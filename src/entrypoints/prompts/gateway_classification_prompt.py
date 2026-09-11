"""
Gateway classification prompt template for LLM
"""

GATEWAY_CLASSIFICATION_PROMPT = """You are given a gateway configuration YAML file.

Please identify all entry points (routes) and classify them as either public/external or internal, according to the following guidelines:

Entry points should be considered public/external if, for example:
- There are no IP address restrictions; the path is accessible from the public network.
- There are no filters restricting requests by HTTP status (e.g., not blocked by 403/401).
- The route has explicit configuration tags such as `expose`, `external`, or `public`.
- There are no authentication or role-based access restrictions.
- The route is marked as a public-facing API.

Entry points should be considered internal if, for example:
- The route is subject to IP whitelisting or limited to private/internal networks.
- Access is restricted to admins, internal services, or specific roles.
- Internal headers, tokens, or specific referers are required that would not be available to public users.
- The route is protected by 403/401 or custom filters blocking ordinary users.
- The route is labeled as `internal`, `private`, `admin`, or similar.
- It is described as "for admin/internal use only," a service-only API, or a management endpoint.

Your task:
- List all public/external entry points.
- Then, list all internal entry points.
- No explanation or reasoning is necessary; just the lists.

Tips:
- An entry with explicit forwarding rules is definitely labeled as external, even if it appears to be an admin service.
- You only need to focus on URL-level forwarding rules, without concerning yourself with host-level forwarding rules.
- The output format must be a standard JSON string, not a code block starting with ```
- If there is a specific blacklist path, you must output it into the internal entries.

The gateway config YAML is below:
{input}
"""
