"""Check phone numbers via MicroSIP.

This script reads a CSV file containing phone numbers and tries to place
calls using the locally installed MicroSIP softphone.  It assumes that
MicroSIP is installed on Windows and that command-line control is enabled.

Example usage::

    python check_numbers.py numbers.csv --output results.csv

The CSV input is expected to contain at least one column with the phone
numbers.  By default the first column is used, but another column can be
selected via the ``--column`` option.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, run
from typing import Iterable, Iterator, List, Optional, Tuple

# MicroSIP stores its log in the user's AppData folder by default.
DEFAULT_MICROSIP_PATH = r"C:\Program Files\MicroSIP\microsip.exe"
DEFAULT_LOG_FILE = (
    Path(os.environ.get("APPDATA", "")) / "MicroSIP" / "microsip.log"
)

SUCCESS_KEYWORDS = (
    "established",
    "connected",
    "answered",
    "in call",
)

FAILURE_KEYWORDS = (
    "failed",
    "busy",
    "declined",
    "forbidden",
    "not found",
    "unreachable",
    "timeout",
)


@dataclass
class CallResult:
    """Represents the outcome of a MicroSIP call attempt."""

    number: str
    status: str
    details: str

    @property
    def succeeded(self) -> bool:
        return self.status == "success"


class LogTail:
    """Utility class to read new lines appended to a log file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._position = 0

    def ensure_exists(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(
                f"No se encontró el archivo de log de MicroSIP en '{self.path}'."
            )

    def read_new_lines(self) -> List[str]:
        self.ensure_exists()
        with self.path.open("r", encoding="utf-8", errors="ignore") as handle:
            handle.seek(self._position)
            lines = handle.readlines()
            self._position = handle.tell()
        return [line.strip() for line in lines if line.strip()]


def parse_arguments(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv",
        type=Path,
        help="Ruta del archivo CSV con los teléfonos a validar.",
    )
    parser.add_argument(
        "--column",
        default=0,
        help=(
            "Nombre o índice (empezando en 0) de la columna que contiene el "
            "número de teléfono."
        ),
    )
    parser.add_argument(
        "--microsip",
        type=Path,
        default=Path(DEFAULT_MICROSIP_PATH),
        help="Ruta al ejecutable de MicroSIP (microsip.exe).",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_FILE,
        help="Ruta al archivo de log de MicroSIP.",
    )
    parser.add_argument(
        "--sip-prefix",
        default="",
        help="Prefijo a anteponer a cada número (por ejemplo 'sip:').",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=5.0,
        help="Segundos a esperar tras lanzar la llamada antes de colgar.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Tiempo máximo en segundos para esperar la respuesta en el log.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Archivo CSV donde guardar el resultado (opcional).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def load_numbers(csv_path: Path, column: str | int) -> Iterator[str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"El archivo CSV '{csv_path}' no existe.")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        headers: Optional[List[str]] = None
        index: Optional[int] = None

        for row_number, row in enumerate(reader):
            if not row:
                continue

            if row_number == 0:
                headers = row
                if isinstance(column, str):
                    if column not in headers:
                        raise ValueError(
                            f"La columna '{column}' no se encuentra en el archivo CSV."
                        )
                    index = headers.index(column)
                    continue
                if isinstance(column, int):
                    index = column
                else:
                    raise TypeError("La columna debe ser un nombre (str) o índice (int).")

            if index is None:
                raise RuntimeError("No se pudo determinar la columna con los números.")

            if index >= len(row):
                raise ValueError(
                    f"La fila {row_number + 1} no tiene la columna solicitada."
                )

            number = row[index].strip()
            if number:
                yield number


def run_microsip_command(executable: Path, *args: str) -> CompletedProcess[str]:
    if not executable.exists():
        raise FileNotFoundError(
            f"No se encontró MicroSIP en '{executable}'. Verifique la ruta."
        )

    try:
        return run(
            [str(executable), *args],
            check=True,
            text=True,
            capture_output=True,
        )
    except CalledProcessError as exc:
        raise RuntimeError(
            "Fallo al ejecutar MicroSIP: "
            f"{exc}. Salida: {exc.stdout or ''} {exc.stderr or ''}"
        ) from exc


def wait_for_log_update(
    log_tail: LogTail, number: str, timeout: float
) -> Tuple[str, str]:
    """Waits for MicroSIP log entries referring to ``number``.

    Returns a tuple ``(status, details)`` where status is ``"success"``,
    ``"failed"`` o ``"unknown"``.
    """

    deadline = time.time() + timeout
    lines: List[str] = []
    while time.time() < deadline:
        new_lines = log_tail.read_new_lines()
        if new_lines:
            lines.extend(new_lines)
            relevant = [line for line in new_lines if number in line]
            if relevant:
                lower = " ".join(relevant).lower()
                if any(keyword in lower for keyword in SUCCESS_KEYWORDS):
                    return "success", relevant[-1]
                if any(keyword in lower for keyword in FAILURE_KEYWORDS):
                    return "failed", relevant[-1]
        time.sleep(0.5)

    if lines:
        last_line = lines[-1]
        return "unknown", last_line
    return "unknown", "No se encontró información en el log."


def check_number(
    executable: Path,
    log_tail: LogTail,
    number: str,
    prefix: str,
    wait_time: float,
    timeout: float,
) -> CallResult:
    target = f"{prefix}{number}"
    print(f"Marcando {target}...")
    run_microsip_command(executable, "/call", target)
    time.sleep(wait_time)
    run_microsip_command(executable, "/hangup")
    status, details = wait_for_log_update(log_tail, number, timeout)
    print(f"Resultado para {number}: {status} ({details})")
    return CallResult(number=number, status=status, details=details)


def save_results(path: Path, results: Iterable[CallResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["number", "status", "details"])
        for result in results:
            writer.writerow([result.number, result.status, result.details])


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_arguments(argv)

    column: str | int
    if isinstance(args.column, str) and args.column.isdigit():
        column = int(args.column)
    else:
        column = args.column

    numbers = list(load_numbers(args.csv, column))
    if not numbers:
        print("No se encontraron números en el CSV.")
        return 1

    log_tail = LogTail(args.log_file)
    log_tail.ensure_exists()

    results: List[CallResult] = []
    for number in numbers:
        try:
            result = check_number(
                args.microsip,
                log_tail,
                number,
                args.sip_prefix,
                args.wait,
                args.timeout,
            )
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Error al verificar {number}: {exc}")
            result = CallResult(number=number, status="failed", details=str(exc))
        results.append(result)

    success = sum(1 for result in results if result.succeeded)
    failure = sum(1 for result in results if result.status == "failed")
    unknown = len(results) - success - failure

    print("Resumen:")
    print(f"  Éxito:   {success}")
    print(f"  Fallo:   {failure}")
    print(f"  Desconocido: {unknown}")

    if args.output:
        save_results(args.output, results)
        print(f"Resultados guardados en {args.output}.")

    return 0 if success == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
