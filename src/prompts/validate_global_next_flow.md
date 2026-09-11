Here is the next **cross-service** flow to analyze. Keep the context from the flows you already reviewed (shared services, endpoints, authz functions you already inspected — do not re-request code you have already seen).

{flow_summary}

Apply the same procedure as before:
- identify the privileged `[SINK]` service and operation,
- trace the attacker-controlled value across each `[CROSS-SERVICE]` hop,
- locate authN/authZ checks in *any* service on the path (gateway/entry annotation, pre-call check in the caller, router middleware / interceptor on the receiver, inline check in the handler or sink),
- decide whether the *specific* escalated property (role, resource id, target user, …) is left unchecked where it should have been.

Respond in the same format, using `<assessment>`, `<constraints>`, `<request>` (keep `services/<svc>/` prefixes), and `<reasoning>` tags.
