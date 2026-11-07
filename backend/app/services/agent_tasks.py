"""任务权限、租约、确认版本与业务事务。模型输出从不直接写业务表。"""
import hashlib
import json
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from app.db.base import utcnow
from app.models import AgentTask, AgentExecution, User, Ticket, Comment, Activity
from app.models.knowledge import KnowledgeDocument
from app.errors import AppError
from app.services.tickets import TicketService
from app.sla_scheduler import after_commit


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def task_data(task):
    return {key:getattr(task,key) for key in ('id','ticket_id','mode','instruction','status','generation',
        'rounds','tool_calls','proposal_version','content','sources','trace','expires_at','result_id','error','created_at')}


async def scope(session, user_id, ticket_id, *, closed=False):
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    ticket = await session.scalar(select(Ticket).where(Ticket.id == ticket_id).with_for_update().execution_options(populate_existing=True))
    if not user or not user.is_active or user.role != 'agent' or not ticket or ticket.assignee_id != user_id:
        raise AppError(403, 40002, '仅当前负责客服可访问该任务')
    if not closed and ticket.status == 'closed':
        raise AppError(409, 41001, '工单已关闭，无法执行Agent任务')
    return user, ticket


async def fingerprint(session, ticket, user):
    # 沟通记录无编辑接口；当前读最高ID避免REPEATABLE READ的旧快照。
    last_comment = await session.scalar(select(Comment.id).where(Comment.ticket_id == ticket.id).order_by(Comment.id.desc()).limit(1).with_for_update())
    last_activity = await session.scalar(select(Activity.id).where(Activity.ticket_id == ticket.id).order_by(Activity.id.desc()).limit(1).with_for_update())
    return digest([ticket.title,ticket.description,ticket.status,ticket.assignee_id,ticket.priority,
        ticket.category,last_comment,last_activity,user.password_hash])


class AgentTasks:
    def __init__(self, factory, settings):
        self.factory, self.settings = factory, settings

    @asynccontextmanager
    async def locked(self, task_id, user_id):
        async with self.factory() as session, session.begin():
            initial = await session.get(AgentTask, task_id)
            if not initial or initial.user_id != user_id:
                raise AppError(404, 41002, '任务不存在')
            user, ticket = await scope(session, user_id, initial.ticket_id, closed=True)
            task = await session.scalar(select(AgentTask).where(AgentTask.id == task_id).with_for_update().execution_options(populate_existing=True))
            yield session, user, ticket, task

    async def create(self, ticket_id, user_id, payload):
        async with self.factory() as session, session.begin():
            user, ticket = await scope(session, user_id, ticket_id)
            old = await session.scalar(select(AgentTask).where(AgentTask.user_id == user_id, AgentTask.request_id == payload.request_id).with_for_update())
            if old:
                if (old.ticket_id,old.mode,old.instruction) != (ticket_id,payload.mode,payload.instruction.strip()):
                    raise AppError(409, 41003, '请求标识已用于其他输入')
                return task_data(old)
            if not payload.instruction.strip():
                raise AppError(400,41004,'请输入任务要求')
            task = AgentTask(id=uuid4().hex, user_id=user_id, ticket_id=ticket_id,
                request_id=payload.request_id, mode=payload.mode, instruction=payload.instruction.strip(),
                fingerprint=await fingerprint(session,ticket,user))
            session.add(task)
            await session.flush()
            return task_data(task)

    async def get(self, task_id, user_id):
        async with self.locked(task_id,user_id) as (session,user,ticket,task):
            if task.status == 'waiting_confirmation':
                problem = await self.invalid(session,user,ticket,task)
                if problem:
                    task.status,task.error = problem
            return task_data(task)

    async def list(self, ticket_id, user_id, limit=10, before=None):
        async with self.factory() as session, session.begin():
            await scope(session,user_id,ticket_id,closed=True)
            query = select(AgentTask).where(AgentTask.ticket_id == ticket_id,AgentTask.user_id == user_id)
            if before:
                cursor = await session.get(AgentTask,before)
                if not cursor or cursor.user_id != user_id or cursor.ticket_id != ticket_id:
                    raise AppError(400,41002,'无效分页游标')
                query = query.where((AgentTask.created_at < cursor.created_at) |
                    ((AgentTask.created_at == cursor.created_at) & (AgentTask.id < cursor.id)))
            rows = await session.scalars(query.order_by(AgentTask.created_at.desc(),AgentTask.id.desc()).limit(limit))
            return [task_data(task) for task in rows]

    async def invalid(self, session, user, ticket, task):
        if task.expires_at and task.expires_at <= utcnow():
            return 'expired','确认已过期，请新建任务'
        if ticket.status == 'closed' or task.fingerprint != await fingerprint(session,ticket,user):
            return 'stale','工单内容或状态已变化，请新建任务'
        for source in task.sources:
            doc = await session.get(KnowledgeDocument,source['document_id'],populate_existing=True,with_for_update=True)
            if not doc or doc.active_version != source['version']:
                return 'stale','参考资料已更新，请新建任务'
        return None

    async def start(self, task_id, user_id):
        problem = None
        async with self.locked(task_id,user_id) as (session,user,ticket,task):
            if task.status not in ('pending','running','failed'):
                return task_data(task), False
            if task.status == 'running' and task.lease_until and task.lease_until > utcnow():
                raise AppError(409,41005,'任务正在运行，请查询进度，暂勿重试')
            problem = await self.invalid(session,user,ticket,task)
            if problem:
                task.status, task.error = problem
            else:
                other = await session.scalar(select(AgentTask.id).where(AgentTask.user_id==user_id,
                    AgentTask.id!=task_id,AgentTask.status=='running',AgentTask.lease_until>utcnow()).limit(1).with_for_update())
                if other:
                    raise AppError(429,41006,'已有任务运行中，请稍后重试')
                task.status,task.error = 'running',None
                task.generation += 1
                task.lease_until = utcnow()+timedelta(seconds=self.settings.agent_timeout+30)
            data = task_data(task)
        if problem:
            raise AppError(409,41007,problem[1])
        return data, True

    async def progress(self, task_id, user_id, generation, *, consume=None, event=None):
        async with self.locked(task_id,user_id) as (session,user,ticket,task):
            if task.status != 'running' or task.generation != generation or task.lease_until <= utcnow():
                raise AppError(409,41008,'任务执行已取消或租约失效')
            if task.fingerprint != await fingerprint(session,ticket,user) or ticket.status == 'closed':
                raise AppError(409,41007,'工单已变化，请新建任务')
            if consume:
                field,maximum = ('rounds',6) if consume == 'model' else ('tool_calls',8)
                if getattr(task,field) >= maximum:
                    raise AppError(409,41009,'任务已达到模型或工具调用上限，请人工处理')
                setattr(task,field,getattr(task,field)+1)
            if event:
                task.trace = (task.trace+[event])[-24:]

    async def finish_run(self, task_id, user_id, generation, result=None, error=None):
        async with self.locked(task_id,user_id) as (session,user,ticket,task):
            if task.generation != generation or task.status != 'running':
                return task_data(task)
            task.lease_until = None
            problem = await self.invalid(session,user,ticket,task)
            if problem:
                task.status,task.error = problem
            elif error:
                task.status,task.error = 'failed',error[:300]
            else:
                task.content = result.get('content','')
                task.sources = result.get('sources',[])
                task.status = result['status']
                if task.status == 'waiting_confirmation':
                    task.proposal_version += 1
                    task.content_hash = digest([task.mode,task.content])
                    task.expires_at = utcnow()+timedelta(seconds=self.settings.agent_confirmation_seconds)
                    problem = await self.invalid(session,user,ticket,task)
                    if problem:
                        task.status,task.error = problem
            return task_data(task)

    async def edit(self, task_id, user_id, payload):
        error = None
        async with self.locked(task_id,user_id) as (session,user,ticket,task):
            if task.status != 'waiting_confirmation' or task.proposal_version != payload.version:
                raise AppError(409,41010,'提案已变化，请重新查看')
            error = await self.invalid(session,user,ticket,task)
            if error:
                task.status,task.error = error
            else:
                if not payload.content.strip():
                    raise AppError(400,41004,'内容不能为空')
                task.content = payload.content.strip()
                task.proposal_version += 1
                task.content_hash = digest([task.mode,task.content])
                # 编辑不延长原确认期限。
            data = task_data(task)
        if error:
            raise AppError(409,41007,error[1])
        return data

    async def cancel(self, task_id, user_id, *, reject=False):
        async with self.locked(task_id,user_id) as (_,_,_,task):
            if task.status in ('succeeded','completed','rejected','cancelled','expired','stale'):
                return task_data(task)
            if reject and task.status != 'waiting_confirmation':
                raise AppError(409,41010,'当前没有待确认操作')
            task.status = 'rejected' if reject else 'cancelled'
            task.generation += 1
            task.lease_until = None
            return task_data(task)

    async def confirm(self, task_id, user_id, version):
        error, scheduled = None, None
        async with self.locked(task_id,user_id) as (session,user,ticket,task):
            # 成功重试仍鉴权，但不再因成功写入自身改变了指纹而拒绝。
            if task.status == 'succeeded':
                if task.proposal_version != version:
                    raise AppError(409,41010,'确认版本不一致')
                return task_data(task)
            if task.status != 'waiting_confirmation' or task.proposal_version != version:
                raise AppError(409,41010,'当前提案不能确认，请刷新任务')
            error = await self.invalid(session,user,ticket,task)
            if error:
                task.status,task.error = error
            else:
                if task.content_hash != digest([task.mode,task.content]):
                    raise AppError(409,41010,'确认内容校验失败')
                service = TicketService(session,self.settings)
                if task.mode == 'internal_summary':
                    comment = await service.add_note_in_transaction(ticket,task.content,actor=user)
                else:
                    comment = await service.add_comment_in_transaction(ticket,user_id,task.content,actor=user)
                    if ticket.sla_snapshot:
                        scheduled = (ticket.id,ticket.sla_snapshot.version)
                session.add(AgentExecution(task_id=task.id,proposal_version=version,
                    content_hash=task.content_hash,comment_id=comment.id))
                task.status,task.result_id = 'succeeded',comment.id
                await session.flush()
            data = task_data(task)
        if error:
            raise AppError(409,41007,error[1])
        if scheduled:
            await after_commit(*scheduled,settings=self.settings)
        return data
