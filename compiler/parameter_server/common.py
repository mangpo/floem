from floem import *

class param_message(State):
    group_id = Field(Int)
    member_id = Field(Int)
    start_id = Field(Uint(64))
    n = Field(Int)
    parameters = Field(Array(Int))
    layout = [group_id, member_id, start_id, n, parameters]

class param_message_out(State):
    group_id = Field(Int)
    member_id = Field(Int)
    n = Field(Int)
    parameters = Field(Array(Int))
    layout = [group_id, n, parameters]