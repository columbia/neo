// Gateway service: public-facing. Forwards a caller-supplied role to an
// internal permissions service with no check of its own -> privilege
// escalation, 2 hops downstream.
package main

import (
	"fmt"
	"io"
	"net/http"
)

const permissionsSvc = "http://permissions-svc:8081"

func updateProfile(w http.ResponseWriter, r *http.Request) {
	role := r.URL.Query().Get("role") // attacker-controlled
	uid := r.URL.Query().Get("uid")

	url := permissionsSvc + "/internal/check?uid=" + uid + "&role=" + role
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
