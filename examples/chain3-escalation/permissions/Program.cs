// Permissions service: sits between the gateway and the data layer to
// authorize role changes, but performs no actual check -- it just forwards
// the request straight through to the internal user service.
using System.Net.Http;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

var client = new HttpClient();
const string UsersSvc = "http://users-svc:9000";

app.MapGet("/internal/check", async (string role, string uid) =>
{
    // no real permission validation -- forwards straight through
    var url = UsersSvc + "/internal/setRole?uid=" + uid + "&role=" + role;
    var resp = await client.GetAsync(url);
    return await resp.Content.ReadAsStringAsync();
});

app.Run("http://localhost:8081");
