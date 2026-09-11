"""Channel-identifier parsing and cross-language matching."""

from interlang.channels import (
    GRPC,
    HTTP,
    KAFKA,
    Channel,
    Endpoint,
    match_channel,
)


def ep(path, method=None, kind=HTTP, topic=None):
    return Endpoint(service="svc", kind=kind, method=method, path=path, topic=topic,
                    handler_id=f"h@f.py:1", handler_name="h", file="f.py", line=1)


def test_parse_full_url():
    c = Channel.parse("http://localhost:5000/setUserRole", "http")
    assert c.kind == HTTP
    assert c.host == "localhost:5000"
    assert c.path == "/setUserRole"
    assert c.host_is_local is True


def test_parse_bare_path_and_service_host():
    c = Channel.parse("http://user-mgmt/api/roles", "http")
    assert c.path == "/api/roles"
    assert c.host == "user-mgmt"
    assert c.host_is_local is False


def test_parse_topic_and_grpc():
    assert Channel.parse("user.events.role-changed", "kafka").topic == "user.events.role-changed"
    g = Channel.parse("user.UserService/SetUserRole")
    assert g.kind == GRPC and g.topic == "user.UserService/SetUserRole"


def test_exact_path_match_scores_high():
    c = Channel.parse("http://localhost:5000/setUserRole", "http", method="POST")
    ranked = match_channel(c, [ep("/setUserRole", "POST")], service_tokens=["user-mgmt"])
    assert ranked and ranked[0][1] >= 0.9


def test_templated_segment_matches():
    c = Channel.parse("/users/42/role", "http")
    ranked = match_channel(c, [ep("/users/{id}/role")])
    assert ranked and ranked[0][1] >= 0.4


def test_suffix_match_with_base_path_stripped():
    c = Channel.parse("http://svc/api/v1/orders/7/pay", "http")
    ranked = match_channel(c, [ep("/orders/{id}/pay")], base_path="/api/v1")
    assert ranked and ranked[0][1] > 0.0


def test_method_mismatch_is_penalised():
    c = Channel.parse("/setUserRole", "http", method="GET")
    ranked = match_channel(c, [ep("/setUserRole", "POST")], min_score=0.0)
    assert ranked and ranked[0][1] < 0.5


def test_unrelated_path_does_not_match():
    c = Channel.parse("/orders", "http")
    assert match_channel(c, [ep("/users/{id}")]) == []


def test_host_only_channel_matches_aliased_service():
    # gateway does requests.post(BASE + dyn_path); only BASE is constant
    c = Channel.parse("http://users-svc:9000", "http", method="POST")
    ranked = match_channel(c, [ep("/internal/setRole", "POST")],
                           service_tokens=["users-svc", "localhost:9000"])
    assert ranked and 0.5 <= ranked[0][1] <= 0.8
    # ...but not to an unrelated service
    assert match_channel(c, [ep("/x", "POST")], service_tokens=["billing"]) == []


def test_kafka_topic_matching():
    c = Channel.parse("order-events", "kafka")
    assert match_channel(c, [ep("", kind=KAFKA, topic="order-events")])[0][1] == 1.0
    assert match_channel(c, [ep("", kind=KAFKA, topic="user-events")]) == []


def test_grpc_method_matching():
    c = Channel.parse("user.UserService/SetUserRole", GRPC)
    ranked = match_channel(c, [ep("", kind=GRPC, topic="user.UserService/SetUserRole")])
    assert ranked and ranked[0][1] == 1.0
