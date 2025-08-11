from __future__ import annotations

from pathlib import Path
import json
import typer

from src.agents.pdf_parser_agent import parse_pdf, XmlParseError

app = typer.Typer(add_completion=False)


PDFS = [
    Path("data/exemplos/pdf/35240361412110067225650530000913141224108397-nfe.pdf"),
    Path("data/exemplos/pdf/35241261412110017716650550000772311960663144-nfe.pdf"),
    Path("data/exemplos/pdf/NFe35250219361558000554550100002752421223005850-nfe.pdf"),
    Path("data/exemplos/pdf/NFe35250619361558000554550100002872271243867093-nfe.pdf"),
]


@app.command()
def main(directory: Path | None = typer.Option(None, "--dir", help="Diretório para varrer PDFs")):
    files: list[Path]
    if directory and directory.exists():
        files = sorted(p for p in directory.rglob("*.pdf"))
        if not files:
            typer.secho(f"Nenhum PDF encontrado em: {directory}", fg=typer.colors.YELLOW)
            raise typer.Exit(0)
    else:
        files = PDFS

    for pdf in files:
        print("=" * 80)
        print(f"Arquivo: {pdf}")
        try:
            payload = parse_pdf(pdf)
            print(json.dumps(payload.model_dump(), ensure_ascii=False, indent=2))
        except XmlParseError as e:
            typer.secho(f"Falha ao extrair via LLM: {e}", fg=typer.colors.RED)
            continue
        except Exception as e:
            typer.secho(f"Falha inesperada em {pdf}: {e}", fg=typer.colors.RED)
            continue


if __name__ == "__main__":
    app()


