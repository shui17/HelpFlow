class HelpFlowError(Exception):
    """所有 HelpFlow 业务异常的基类。"""


class UserNotFoundError(HelpFlowError):
    """指定用户不存在。"""


class TicketNotFoundError(HelpFlowError):
    """指定工单不存在。"""


class InvalidUserDataError(HelpFlowError):
    """用户数据不符合业务要求。"""


class InvalidTicketDataError(HelpFlowError):
    """工单或回复数据不符合业务要求。"""


class InvalidStatusTransitionError(HelpFlowError):
    """工单状态不能按照请求的方式流转。"""


class TicketNotEditableError(HelpFlowError):
    """工单已经开始处理或已分配，不能修改内容。"""
