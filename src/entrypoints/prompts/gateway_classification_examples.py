"""
Gateway classification examples for few-shot learning
"""

GATEWAY_EXAMPLES = [
    {
        "input": "spring:\n  cloud:\n    gateway:\n      routes:\n        - id: health_check\n          uri: lb://status\n          predicates:\n            - Path=/actuator/health\n        - id: admin_interface\n          uri: no://blackhole\n          predicates:\n            - Path=/internal/admin/**\n          filters:\n            - SetStatus=403",
        "output": '{"external_entries": ["/actuator/health"], "internal_entries": ["/internal/admin/**"]}',
    },
    {
        "input": "spring:\n  cloud:\n    gateway:\n      routes:\n        - id: public_api\n          uri: lb://public-api\n          predicates:\n            - Path=/api/**\n        - id: internal_devtool\n          uri: lb://devtool\n          predicates:\n            - Path=/devtool/**\n          filters:\n            - AddResponseHeader=X-Internal-Only, true",
        "output": '{"external_entries": ["/api/**"], "internal_entries": ["/devtool/**"]}',
    },
    {
        "input": "spring:\n  cloud:\n    gateway:\n      routes:\n        - id: user_center\n          uri: lb://user\n          predicates:\n            - Path=/user/**\n        - id: secret_data\n          uri: lb://secret\n          predicates:\n            - Path=/secret/data/**\n          filters:\n            - IpWhitelist=10.0.0.0/8",
        "output": '{"external_entries": ["/user/**"], "internal_entries": ["/secret/data/**"]}',
    },
    {
        "input": "spring:\n  cloud:\n    gateway:\n      routes:\n        - id: blog\n          uri: lb://blog-service\n          predicates:\n            - Path=/blog/**\n        - id: analytics\n          uri: lb://analytics-service\n          predicates:\n            - Path=/internal/analytics/**",
        "output": '{"external_entries": ["/blog/**", "/internal/analytics/**"], "internal_entries": []}',
    },
    {
        "input": "spring:\n  cloud:\n    gateway:\n      routes:\n        - id: forum\n          uri: lb://forum\n          predicates:\n            - Path=/forum/**\n        - id: admin_api\n          uri: lb://admin\n          predicates:\n            - Path=/admin/**\n          filters:\n            - SetResponseStatus=403",
        "output": '{"external_entries": ["/forum/**"], "internal_entries": ["/admin/**"]}',
    },
    {
        "input": "spring:\n  cloud:\n    gateway:\n      routes:\n        - id: blog\n          uri: lb://blog\n          predicates:\n            - Path=/blog/**\n        - id: forum\n          uri: lb://forum\n          predicates:\n            - Path=/forum/**",
        "output": '{"external_entries": ["/blog/**", "/forum/**"], "internal_entries": []}',
    },
]
