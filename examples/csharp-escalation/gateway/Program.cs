// Gateway service: public-facing. Forwards a caller-supplied role to the
// internal user service with no authorization check -> privilege escalation.
using System.Net.Http;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

var client = new HttpClient();
const string UsersSvc = "http://localhost:9000";

app.MapGet("/api/profile", async (string role, string uid) =>
{
    // no check that the caller may set roles
    var url = UsersSvc + "/internal/setRole?uid=" + uid + "&role=" + role;
    var resp = await client.GetAsync(url);
    return await resp.Content.ReadAsStringAsync();
});

app.Run("http://localhost:8080");
