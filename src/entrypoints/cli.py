"""
CLI Interface for gateway YAML entry point detection with LLM classification
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description='Detect entry points from gateway YAML files using LLM classification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan codebase with LLM classification
  python -m entrypoints --codebase /path/to/app

  # Output summary format (default)
  python -m entrypoints --codebase /path/to/app --format summary

  # Output JSON format
  python -m entrypoints --codebase /path/to/app --format json

  # Save results to file
  python -m entrypoints --codebase /path/to/app --output results.json

  # Custom LLM provider
  python -m entrypoints --codebase /path/to/app --provider anthropic --model claude-3-5-sonnet-20241022
"""
    )

    parser.add_argument(
        '--codebase',
        required=True,
        type=Path,
        help='Path to codebase root directory'
    )

    parser.add_argument(
        '--output',
        type=Path,
        help='Output file path (default: stdout)'
    )

    parser.add_argument(
        '--format',
        choices=['json', 'summary'],
        default='summary',
        help='Output format (default: summary)'
    )

    parser.add_argument(
        '--provider',
        default='anthropic',
        help='LLM provider (default: anthropic)'
    )

    parser.add_argument(
        '--model',
        default='claude-3-5-sonnet-20241022',
        help='LLM model (default: claude-3-5-sonnet-20241022)'
    )

    args = parser.parse_args()

    # Validate codebase path
    if not args.codebase.exists():
        print(f"Error: Codebase path does not exist: {args.codebase}", file=sys.stderr)
        return 1

    # Import detect_entry_points from __init__.py
    from entrypoints import detect_entry_points

    # Create LLM client (required)
    try:
        from common.llms import LLMClient, get_api_key
    except ImportError:
        print("\n" + "=" * 70, file=sys.stderr)
        print("ERROR: LLM Dependencies Not Available", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("The 'common.llms' module is not available.", file=sys.stderr)
        print("\nTo use this tool, you need:", file=sys.stderr)
        print("  1. Install langchain: pip install langchain-core", file=sys.stderr)
        print("  2. Ensure common.llms module is available", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1

    try:
        api_key = get_api_key(args.provider)
        if not api_key:
            print("\n" + "=" * 70, file=sys.stderr)
            print("ERROR: No API Key Found", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            print(f"No API key found for provider: {args.provider}", file=sys.stderr)
            print("\nTo fix this, set your API key:", file=sys.stderr)
            if args.provider.lower() == 'anthropic':
                print("  export ANTHROPIC_API_KEY='your-api-key-here'", file=sys.stderr)
            elif args.provider.lower() == 'openai':
                print("  export OPENAI_API_KEY='your-api-key-here'", file=sys.stderr)
            else:
                print(f"  export {args.provider.upper()}_API_KEY='your-api-key-here'", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            return 1

        llm_client = LLMClient(args.provider, args.model, api_key)
        print(f"✓ Using LLM: {args.provider}/{args.model}")
    except Exception as e:
        print("\n" + "=" * 70, file=sys.stderr)
        print("ERROR: Failed to Create LLM Client", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1

    # Run detection
    print(f"Scanning codebase: {args.codebase}")
    result = detect_entry_points(
        codebase_root=args.codebase,
        llm_client=llm_client
    )

    # Format output
    if args.format == 'json':
        output_str = _format_json(result)
    else:
        output_str = _format_summary(result)

    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_str)
        print(f"\nResults written to: {args.output}")
    else:
        print("\n" + output_str)

    return 0


def _format_json(result) -> str:
    """Format result as JSON"""
    output_data = result.to_dict()
    return json.dumps(output_data, indent=2)


def _format_summary(result) -> str:
    """Format result as human-readable summary"""
    lines = []

    lines.append("=" * 70)
    lines.append(" " * 20 + "ENTRY POINT DETECTION RESULTS")
    lines.append("=" * 70)

    # Detection metadata
    lines.append(f"\nDetection Method: {result.detection_method.value.upper()}")
    if hasattr(result, 'gateway_file') and result.gateway_file:
        lines.append(f"Gateway File: {result.gateway_file}")
    lines.append(f"Languages: {', '.join(result.languages_detected) if result.languages_detected else 'None'}")

    # Overall stats
    external = [ep for ep in result.entry_points if ep.type.value == 'external']
    internal = [ep for ep in result.entry_points if ep.type.value == 'internal']

    lines.append(f"\nTotal Entry Points: {len(result.entry_points)}")
    lines.append(f"  External (Public): {len(external)}")
    lines.append(f"  Internal (Private): {len(internal)}")

    # External entry points
    if external:
        lines.append("\n" + "-" * 70)
        lines.append("EXTERNAL ENTRY POINTS (Publicly Accessible)")
        lines.append("-" * 70)
        for ep in external:
            lines.append(f"\n  Path: {ep.path or 'N/A'}")
            lines.append(f"  Protocol: {ep.protocol.value.upper()}")
            lines.append(f"  Confidence: {ep.confidence:.0%}" if ep.confidence else "  Confidence: N/A")
            if ep.method:
                lines.append(f"  HTTP Method: {ep.method}")
            lines.append(f"  ID: {ep.function_id}")

    # Internal entry points
    if internal:
        lines.append("\n" + "-" * 70)
        lines.append("INTERNAL ENTRY POINTS (Private/Admin)")
        lines.append("-" * 70)
        for ep in internal:
            lines.append(f"\n  Path: {ep.path or 'N/A'}")
            lines.append(f"  Protocol: {ep.protocol.value.upper()}")
            lines.append(f"  Confidence: {ep.confidence:.0%}" if ep.confidence else "  Confidence: N/A")
            if ep.method:
                lines.append(f"  HTTP Method: {ep.method}")
            lines.append(f"  ID: {ep.function_id}")

    # Warnings and errors
    if result.warnings:
        lines.append("\n" + "!" * 70)
        lines.append("WARNINGS")
        lines.append("!" * 70)
        for warning in result.warnings:
            lines.append(f"  ⚠ {warning}")

    if hasattr(result, 'errors') and result.errors:
        lines.append("\n" + "X" * 70)
        lines.append("ERRORS")
        lines.append("X" * 70)
        for error in result.errors:
            lines.append(f"  ✗ {error}")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)


if __name__ == '__main__':
    exit(main())
