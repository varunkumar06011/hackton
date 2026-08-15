from orders.models import AuditLog


def create_audit_entry(order_id, event_ids, events_detail, rule, explanation, prev_state, final_state):
    return AuditLog.objects.create(
        order_id=order_id,
        event_ids_considered=event_ids,
        events_detail=events_detail,
        resolution_rule=rule,
        rule_explanation=explanation,
        previous_state=prev_state,
        final_state=final_state,
    )


def get_audit_trail(order_id):
    return list(AuditLog.objects.filter(order_id=order_id).order_by("decision_timestamp"))
