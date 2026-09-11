You are a security expert specializing in privilege escalation detection through CodeQL analysis for {language} applications.

Our current detection that identifies privileged operations:
```
{base_query}
```


Task: Please based on the the following description of our target application to identify *additional* privileged operation sinks that should be monitored for potential privilege escalation vulnerabilities. Focus on customized, application-specific operations, such as  business logic, and administrative functions, etc.
<description>
{description}
</description>

Output format:
For each additional sink pattern, provide a CodeQL-compatible regular expression wrapped in <function-name> tags. Focus on functions that could lead to privilege escalation if compromised. Prioritize high-impact operations that attackers would target to gain elevated privileges or access sensitive resources.
<function-name>grant[A-Z].*|revoke[A-Z].*</function-name>
<function-name>admin.*[Aa]ccess.*</function-name>