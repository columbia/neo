// Gateway service: public-facing. Forwards a caller-supplied role to the
// internal user service with no authorization check -> privilege escalation.
#include <httplib.h>
#include <string>

static const std::string kUsersSvcHost = "localhost";
static const int kUsersSvcPort = 9000;

int main() {
    httplib::Server svr;

    svr.Get("/api/profile", [](const httplib::Request &req, httplib::Response &res) {
        std::string role = req.get_param_value("role");    // attacker-controlled
        std::string uid = req.get_param_value("uid");

        // no check that the caller may set roles
        httplib::Client cli(kUsersSvcHost, kUsersSvcPort);
        std::string path = "/internal/setRole?uid=" + uid + "&role=" + role;
        auto resp = cli.Get(path);
        res.set_content(resp ? resp->body : "", "text/plain");
    });

    svr.listen("0.0.0.0", 8080);
    return 0;
}
