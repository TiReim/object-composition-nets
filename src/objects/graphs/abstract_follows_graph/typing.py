from pydantic import BaseModel


class DirectlyFollowsGraphEdgePayload(BaseModel):
    count: int
