// Internal user service. Trusts the gateway completely: whatever role arrives
// on /internal/set-role is written straight into the users table.
const express = require('express');
const mysql = require('mysql2');

const app = express();
app.use(express.json());

const db = mysql.createConnection({ host: 'db', user: 'svc', database: 'app' });

app.post('/internal/set-role', (req, res) => {
  const userId = req.body.userId;
  const role = req.body.role;                     // straight from the request
  // PRIVILEGED: role change via a string-built SQL statement, no authz
  const sql = "UPDATE users SET role = '" + role + "' WHERE id = '" + userId + "'";
  db.query(sql, (err, result) => {
    return res.json({ updated: !err });
  });
});

app.listen(9000);
