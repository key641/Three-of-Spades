from pydantic import BaseModel


class ToolCallResult(BaseModel):
    tool_name: str
    success: bool
    payload: dict

