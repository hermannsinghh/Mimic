package mimic.agent

default allow := false

allow if {
    input.decision.action_type in {"hedge", "hold", "sell", "buy", "reinsure", "cede", "retain"}
    input.decision.quantity * input.entity.price <= input.entity.position_limit
}
