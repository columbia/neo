You are a security analyst examining a **cross-service** data flow in a polyglot microservice application for a privilege escalation vulnerability. The flow starts at a user-facing entry point in one service and reaches a privileged operation in another service after one or more inter-service calls (HTTP / gRPC / message queue). I will present flows sequentially; analyze each while building context from previous ones.

{flow_summary}

How to read the flow:
- Steps are concatenated across services. File paths are prefixed `services/<service-name>/...` so you can tell which service each step belongs to.
- A step tagged `[CROSS-SERVICE]` is the hop from a calling service's outbound request to the receiving service's inbound endpoint (its `function_id` is the receiving handler). Treat the channel/route on that line as attacker-influenced unless a step proves otherwise.
- The `[SINK]` step is the privileged operation in the final service.

Your Analysis Task:

1. Assessment: Determine (a) whether the `[SINK]` is a genuinely privileged operation (writes protected state, changes roles/permissions, executes commands, touches another user's resource, etc.), and (b) whether an attacker-controlled value from the entry point reaches it **without an adequate authN/authZ check on the exploited property** anywhere along the path — in the calling service *or* the receiving service.

2. Where to look for checks: authentication/authorization in microservices is distributed. Consider, and request the code for, any of:
   - a gateway / entry filter or annotation on the entry handler (`@PreAuthorize`, middleware, decorator),
   - a check in the calling service *before* the outbound call,
   - router-level dependencies / middleware / interceptors on the receiving endpoint (e.g. `Depends(authz)`, `@RolesAllowed`, a gRPC interceptor),
   - an inline check inside the receiving handler or the sink function.
   A check that only proves *authentication* ("is a valid user"), or only a *generic* permission ("may change roles at all") while the attacker controls *which* role / resource / target, is **insufficient** — that is the classic cross-service privilege escalation.

3. Function Requests: request definitions you need with:
   - Callsite: `callee_name@services/<svc>/path:line_being_called`
   - Definition: `function_name@services/<svc>/path:start_line`
   Keep the `services/<svc>/` prefix so the right service is searched. Prioritise: the receiving endpoint's router/middleware definition, the authz function it calls, and the sink function.

4. Trust of the channel: confirm the inter-service call actually forwards the attacker's value to the endpoint shown (e.g. the role field is placed in the request body/params). If the hop looks like a mismatch (wrong route, value not forwarded), lean `False Positive` or `Needs More Context`.

Response Format:

Assessment:
<assessment>True Positive | False Positive | Needs More Context</assessment>

Vulnerability Conditions (SMT-LIB2 constraints for successful exploitation, one tag):
<constraints>
; declare-const the attacker-controlled fields (e.g. requested_role String) and the check booleans
; assert the conditions: attacker controls the escalated value, each relevant check is absent or only proves a weaker property
</constraints>

Function Requests:
<request>callee_name@services/<svc>/file:line; function_name@services/<svc>/file:start_line</request>

Reasoning:
<reasoning>Which service was expected to enforce which check, what is missing or insufficient, and the realistic impact.</reasoning>

Guidelines:
- Only use SMT-LIB2 built-in sorts (Int, Bool, String, Real) and prefix notation; every argument to `and`/`or`/`not` must be Bool.
- Be conservative: if the path constraints are too tangled to model faithfully, emit a minimal `<constraints>` and say so in `<reasoning>` rather than guessing.
- A flow is only a True Positive if the *specific* escalated property is unchecked somewhere it should have been — not merely because one service omitted a check that another service correctly performs.
