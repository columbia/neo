// Internal user service, the end of the chain. Trusts the permissions
// service completely: whatever role arrives on /internal/setRole is written
// straight into the users table with a string-built SQL statement.
#include <httplib.h>
#include <sqlite3.h>
#include <string>

static sqlite3 *db = nullptr;

int main() {
    httplib::Server svr;

    svr.Get("/internal/setRole", [](const httplib::Request &req, httplib::Response &res) {
        std::string role = req.get_param_value("role"); // straight from the request
        std::string uid = req.get_param_value("uid");

        // PRIVILEGED: role change with a string-built SQL statement, no authz
        std::string sql = "UPDATE users SET role = '" + role + "' WHERE id = '" + uid + "'";
        sqlite3_exec(db, sql.c_str(), nullptr, nullptr, nullptr);
        res.set_content("ok", "text/plain");
    });

    svr.listen("0.0.0.0", 9000);
    return 0;
}
