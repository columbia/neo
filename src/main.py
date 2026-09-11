import argparse
from common.llms import LLMClient, build_llm, get_api_key, resolve_llm_config, validate_model
from common.helper import create_app_workdir


def create_client(provider: str = None, model: str = None) -> LLMClient:
    """
    Build the LLM client.

    With no arguments, honours NEO_LLM_PROVIDER / NEO_LLM_MODEL (default:
    Claude Sonnet on Vertex AI).  Backends: anthropic, openai, gcloud-anthropic,
    and the agent-CLI backends claude_cli / agy_cli / gemini_cli / cli.
    """
    if provider is None and model is None:
        return build_llm()

    if provider is None:
        provider, _default_model = resolve_llm_config()
    if model is None:
        model = resolve_llm_config()[1]

    if not validate_model(provider, model):
        raise SystemExit(f"Error: unknown model for provider: {provider} / {model}")

    api_key = get_api_key(provider)
    from common.llms import _KEYLESS
    if not api_key and provider not in _KEYLESS:
        raise SystemExit(f"Error: no API key found for provider '{provider}'")

    return LLMClient(provider, model, api_key or "")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='Entry of the analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        """
    )
    
    parser.add_argument('-a', '--app', required=True, help='app name')
    
    # Individual operation flags
    parser.add_argument('-fs', '--find-sinks', action='store_true', help='Find sinks analysis')
    parser.add_argument('-ff', '--find-flows', action='store_true', help='Find flows analysis')
    parser.add_argument('-vf', '--validate-flows', action='store_true', help='Validate flows analysis')
    parser.add_argument('-ep', '--entry-points', action='store_true', help='Detect and classify entry points')
    parser.add_argument('-gf', '--global-flows', action='store_true',
                        help='Cross-service / cross-language: stitch per-service flows into global flows (Algorithm 1)')
    parser.add_argument('--no-codeql', action='store_true',
                        help='With --global-flows, skip the interservice/endpoints CodeQL queries and use heuristics only')
    parser.add_argument('--agent', action='store_true',
                        help='Discover privileged operations with the LLM agent + code-search primitives '
                             '(paper §4.2); replaces the one-shot customize-op step of --find-sinks')

    parser.add_argument('-cr', '--cleanrun', action='store_true', help='Clean up the status and start a new run')

    
    parser.add_argument('--group-by', choices=['sinks', 'sources', 'shared'], default='sinks',
                       help='Grouping method: sinks (default), sources, or shared')
    
    args = parser.parse_args()
    
    from common.helper import (load_env_file, get_app_database_dir, get_app_source_dir,
                               clean_all_status, get_database_language, AnalysisStatus)

    load_env_file()

    appname = args.app
    exit_code = 0

    # Check that at least one operation is specified
    operations = [args.find_flows, args.validate_flows, args.find_sinks,
                  args.entry_points, args.global_flows, args.agent, args.cleanrun]
    if not any(operations):
        print("Error: At least one operation must be specified (--agent, --find-sinks, --find-flows, --validate-flows, --entry-points, or --global-flows)")
        parser.print_help()
        exit(1)

    # A multi-service manifest app has no databases/<appname>; only resolve the
    # single-app paths for the per-app stages that need them.
    _needs_single_app = any([args.find_sinks, args.find_flows, args.entry_points,
                             args.cleanrun]) or (args.validate_flows)
    database = codebase = None

    from common.services import load_application
    _app = load_application(appname)

    if _needs_single_app and not _app.is_multi_service:
        database = get_app_database_dir(appname)
        codebase = get_app_source_dir(appname)
        create_app_workdir(appname)

    if args.cleanrun:
        if _app.is_multi_service:
            for _svc in _app.services:
                try:
                    _lang = get_database_language(_svc.database_dir)
                except Exception:
                    _lang = _svc._safe_language() or "unknown"
                clean_all_status(_lang, _svc.key)
            from common.helper import clean_status
            for _st in (AnalysisStatus.GLOBAL_FLOWS, AnalysisStatus.VALIDATE_GLOBAL_FLOWS):
                clean_status(_app.name, _st)
        else:
            language = get_database_language(database)
            clean_all_status(language, appname)

    if args.agent:
        from agent.run import agent_find_privileged_ops, merge_into_customize_op
        llm = create_client()
        agent_find_privileged_ops(appname, llm)
        merge_into_customize_op(appname)

    if args.find_sinks:
        from sinks.find_sinks import find_sinks_main
        llm = create_client()
        result = find_sinks_main(llm, appname, skip_customize_op=args.agent)
        if isinstance(result, int):
            exit_code = max(exit_code, result)
        
    if args.find_flows:
        from flows.find_flows import find_flow_main
        exit_code = max(exit_code, find_flow_main(database, codebase, appname, args.group_by))

    if args.global_flows:
        from interlang.run import global_flow_main
        exit_code = max(exit_code, global_flow_main(appname, run_codeql=not args.no_codeql))

    if args.validate_flows:
        llm = create_client()
        if _app.is_multi_service:
            from interlang.run import validate_global_flows
            result = validate_global_flows(llm, appname)
        else:
            from flows.validate_flows import validate_flow_main
            result = validate_flow_main(llm, appname)
        if isinstance(result, int):
            exit_code = max(exit_code, result)

    if args.entry_points and _app.is_multi_service:
        print("Note: --entry-points operates on a single service; run it per service "
              "(python main.py --app <service> --entry-points). Skipping.")
    elif args.entry_points:
        from entrypoints import detect_entry_points
        from pathlib import Path
        import json

        # Create LLM client for entry point classification
        llm = create_client()

        # Run detection (gateway-YAML based; see entrypoints/__init__.py)
        print(f"Detecting entry points in: {codebase}")
        result = detect_entry_points(Path(codebase), llm_client=llm)

        # Print summary
        external = [ep for ep in result.entry_points if ep.type.value == 'external']
        internal = [ep for ep in result.entry_points if ep.type.value == 'internal']

        print(f"\n{'='*60}")
        print("Entry Point Detection Summary")
        print(f"{'='*60}")
        print(f"Detection Method: {result.detection_method.value}")
        if result.gateway_file:
            print(f"Gateway File: {result.gateway_file}")
        print(f"Total Entry Points: {len(result.entry_points)}")
        print(f"  External: {len(external)}")
        print(f"  Internal: {len(internal)}")
        print(f"{'='*60}\n")

        # Save results to work directory
        from common.helper import get_app_workdir
        output_path = Path(get_app_workdir(appname)) / "entry_points.json"
        with open(output_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Detailed results saved to: {output_path}")

    raise SystemExit(exit_code)
