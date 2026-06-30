import re

with open('dota2bot/__main__.py', 'r') as f:
    code = f.read()

# Add import
if 'from .statistical_report import add_statistical_report_args, run_statistical_report' not in code:
    code = re.sub(
        r'(from \.sizing_report import .+?\n)',
        r'\1from .statistical_report import add_statistical_report_args, run_statistical_report\n',
        code
    )
    if 'add_statistical_report_args' not in code:
        # Fallback if sizing_report wasn't imported like that
        code = re.sub(
            r'(from \.paper_sizing_report import .+?\n)',
            r'\1from .statistical_report import add_statistical_report_args, run_statistical_report\n',
            code
        )

# Add parser
if 'statistical-report' not in code:
    parser_block = """
    statistical_report = sub.add_parser("statistical-report", help="advanced statistical metrics with bootstrapping")
    add_statistical_report_args(statistical_report)
"""
    code = re.sub(
        r'(    sizing_report = sub\.add_parser\("paper-sizing-report"[^\n]+\n    add_sizing_report_args\(sizing_report\)\n)',
        r'\1' + parser_block,
        code
    )

# Add execute
if 'args.command == "statistical-report"' not in code:
    execute_block = """
    elif args.command == "statistical-report":
        run_statistical_report(
            logs_root=Path(args.logs_root),
            input_name=args.input_name,
            source=args.source,
            sizing=args.sizing,
            bootstrap_samples=args.bootstrap_samples,
            output_format=args.format,
        )
"""
    code = re.sub(
        r'(    elif args\.command == "paper-sizing-report":\n[ \t]+print\(\n[ \t]+run_sizing_report\([\s\S]+?\)\n[ \t]+\)\n)',
        r'\1' + execute_block,
        code
    )

with open('dota2bot/__main__.py', 'w') as f:
    f.write(code)

