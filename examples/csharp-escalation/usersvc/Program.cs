// Internal user service. Trusts the gateway completely: whatever role arrives
// on /internal/setRole is written straight into the users table.
using System.Data.SqlClient;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

var conn = new SqlConnection("Server=db;Database=app;Trusted_Connection=True;");

app.MapGet("/internal/setRole", (string role, string uid) =>
{
    // PRIVILEGED: role change with a string-built SQL statement, no authz
    var sql = "UPDATE Users SET Role = '" + role + "' WHERE Id = '" + uid + "'";
    new SqlCommand(sql, conn).ExecuteNonQuery();
    return Results.Ok();
});

app.Run("http://localhost:9000");
