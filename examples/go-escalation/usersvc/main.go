// Internal user service. Trusts the gateway completely: whatever role arrives
// on /internal/setRole is written straight into the users table.
package main

import (
	"database/sql"
	"fmt"
	"net/http"
)

var db *sql.DB

func setRole(w http.ResponseWriter, r *http.Request) {
	role := r.URL.Query().Get("role") // straight from the request
	userID := r.URL.Query().Get("uid")

	// PRIVILEGED: role change with a string-built SQL statement, no authz
	query := "UPDATE users SET role = '" + role + "' WHERE id = '" + userID + "'"
	_, err := db.Exec(query)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	fmt.Fprintln(w, "ok")
}

func main() {
	http.HandleFunc("/internal/setRole", setRole)
	http.ListenAndServe(":9000", nil)
}
