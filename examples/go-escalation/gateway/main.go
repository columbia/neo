// Gateway service: public-facing. Forwards a caller-supplied role to the
// internal user service with no authorization check -> privilege escalation.
package main

import (
	"fmt"
	"io"
	"net/http"
)

const usersSvc = "http://users-svc:9000"

func updateProfile(w http.ResponseWriter, r *http.Request) {
	role := r.URL.Query().Get("role") // attacker-controlled
	userID := r.URL.Query().Get("uid")

	// no check that the caller may set roles
	url := usersSvc + "/internal/setRole?uid=" + userID + "&role=" + role
	resp, err := http.Get(url)
	if err != nil {
		http.Error(w, err.Error(), 502)
		return
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	fmt.Fprintf(w, "%s", body)
}

func main() {
	http.HandleFunc("/api/profile", updateProfile)
	http.ListenAndServe(":8080", nil)
}
