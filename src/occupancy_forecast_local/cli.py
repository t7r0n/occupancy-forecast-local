from __future__ import annotations

import json
import sys

import typer
from rich.console import Console
from rich.table import Table

from occupancy_forecast_local.dashboard import build_dashboard
from occupancy_forecast_local.engine import forecast, recommend, top_anomalies
from occupancy_forecast_local.fixtures import export_csv, load_fixture, write_demo_fixture
from occupancy_forecast_local.models import ActionName
from occupancy_forecast_local.runner import benchmark, export_demo_pack, run_suite, verify_outputs

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def init_demo(force: bool = typer.Option(False, "--force")) -> None:
    path = write_demo_fixture(force=force)
    csv_path = export_csv()
    console.print({"fixture": str(path), "csv": str(csv_path)})


@app.command()
def forecast_cmd(space_id: str = typer.Option("floor-2", "--space-id")) -> None:
    report = forecast(space_id)
    console.print_json(report.model_dump_json())


@app.command("forecast")
def forecast_alias(space_id: str = typer.Option("floor-2", "--space-id")) -> None:
    forecast_cmd(space_id)


@app.command()
def anomaly(limit: int = typer.Option(10, "--limit")) -> None:
    rows = top_anomalies(limit=limit)
    console.print_json(json.dumps([row.model_dump(mode="json") for row in rows]))


@app.command()
def recommend_cmd(
    space_id: str = typer.Option("floor-4", "--space-id"),
    action: str = typer.Option(ActionName.CLOSE_FRIDAYS.value, "--action"),
) -> None:
    rec = recommend(space_id, ActionName(action))
    console.print_json(rec.model_dump_json())


@app.command("recommend")
def recommend_alias(
    space_id: str = typer.Option("floor-4", "--space-id"),
    action: str = typer.Option(ActionName.CLOSE_FRIDAYS.value, "--action"),
) -> None:
    recommend_cmd(space_id, ActionName(action).value)


@app.command()
def suite() -> None:
    summary = run_suite()
    console.print_json(summary.model_dump_json())


@app.command()
def spaces() -> None:
    fixture = load_fixture()
    table = Table(title="Spaces")
    table.add_column("ID")
    table.add_column("Kind")
    table.add_column("Capacity")
    for space in fixture.spaces:
        table.add_row(space.id, space.kind.value, str(space.capacity))
    console.print(table)


@app.command()
def verify() -> None:
    ok, checks = verify_outputs()
    table = Table(title="Verification")
    table.add_column("Gate")
    table.add_column("Status")
    for key, value in checks.items():
        table.add_row(key, "PASS" if value else "FAIL")
    console.print(table)
    if not ok:
        raise typer.Exit(1)


@app.command()
def dashboard() -> None:
    path = build_dashboard()
    console.print(f"Dashboard written: {path}")


@app.command("benchmark")
def benchmark_cmd(iterations: int = typer.Option(100, "--iterations", min=1)) -> None:
    summary = benchmark(iterations=iterations)
    table = Table(title="Benchmark")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("runs", str(iterations))
    table.add_row("forecast improvement", f"{summary.forecast_improvement:.0%}")
    table.add_row("anomaly precision", f"{summary.anomaly_precision:.0%}")
    table.add_row("capacity calibrated", str(summary.capacity_calibrated))
    table.add_row("pass gates", str(summary.pass_gates))
    console.print(table)


@app.command("export-demo-pack")
def export_demo_pack_cmd() -> None:
    path = export_demo_pack()
    console.print(f"Demo pack written: {path}")


@app.command()
def tool_loop() -> None:
    for line in sys.stdin:
        payload = json.loads(line)
        tool = payload.get("tool")
        args = payload.get("arguments", {})
        if tool == "forecast":
            print(forecast(args.get("space_id", "floor-2")).model_dump_json())
        elif tool == "anomaly":
            rows = top_anomalies(limit=int(args.get("limit", 10)))
            print(json.dumps([row.model_dump(mode="json") for row in rows]))
        elif tool == "recommend":
            rec = recommend(
                args.get("space_id", "floor-4"),
                ActionName(args.get("action", "close-fridays")),
            )
            print(rec.model_dump_json())
        else:
            print(json.dumps({"error": f"unknown tool: {tool}"}))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
