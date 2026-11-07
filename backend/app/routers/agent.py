from fastapi import APIRouter, Request, Query
from app.dependencies import CurrentUser
from app.pagination import EntityId
from app.schemas import ApiResponse
from app.services.agent_tasks import AgentTasks
from app.services.agent_runtime import AgentRuntime
from app.services.agent_types import CreateTask, EditProposal, ProposalVersion

router = APIRouter(tags=['agent'])


def service(request):
    return AgentTasks(request.app.state.session_factory, request.app.state.settings)


@router.post('/tickets/{ticket_id}/agent-tasks')
async def create(ticket_id: EntityId, payload: CreateTask, request: Request, user: CurrentUser):
    return ApiResponse(data=await service(request).create(ticket_id, user.id, payload))


@router.get('/tickets/{ticket_id}/agent-tasks')
async def listing(ticket_id: EntityId, request: Request, user: CurrentUser,
                  limit: int = Query(10, ge=1, le=30), before: str | None = Query(None, max_length=32)):
    return ApiResponse(data=await service(request).list(ticket_id, user.id, limit, before))


@router.get('/agent-tasks/{task_id}')
async def get(task_id: str, request: Request, user: CurrentUser):
    return ApiResponse(data=await service(request).get(task_id, user.id))


@router.post('/agent-tasks/{task_id}/run')
async def run(task_id: str, request: Request, user: CurrentUser):
    return ApiResponse(data=await AgentRuntime(service(request)).run(task_id, user.id))


@router.patch('/agent-tasks/{task_id}/proposal')
async def edit(task_id: str, payload: EditProposal, request: Request, user: CurrentUser):
    return ApiResponse(data=await service(request).edit(task_id, user.id, payload))


@router.post('/agent-tasks/{task_id}/confirm')
async def confirm(task_id: str, payload: ProposalVersion, request: Request, user: CurrentUser):
    task = await AgentRuntime(service(request)).confirm(task_id, user.id, payload.version)
    return ApiResponse(data=task)


@router.post('/agent-tasks/{task_id}/reject')
async def reject(task_id: str, request: Request, user: CurrentUser):
    return ApiResponse(data=await service(request).cancel(task_id, user.id, reject=True))


@router.post('/agent-tasks/{task_id}/cancel')
async def cancel(task_id: str, request: Request, user: CurrentUser):
    return ApiResponse(data=await service(request).cancel(task_id, user.id))
