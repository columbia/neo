// Gateway service: public-facing. Forwards a caller-supplied role to the
// internal user service with no authorization check -> privilege escalation.
const express = require('express');
const axios = require('axios');

const app = express();
app.use(express.json());

const USERS_SVC = 'http://users-svc:9000';

app.post('/api/users/:userId/profile', async (req, res) => {
  const userId = req.params.userId;
  const role = req.body.role;                     // attacker-controlled
  // no check that the caller is allowed to set roles
  const resp = await axios.post(USERS_SVC + '/internal/set-role', {
    userId: userId,
    role: role,
  });
  return res.json(resp.data);
});

app.listen(8080);
