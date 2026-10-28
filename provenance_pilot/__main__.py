import argparse
import json
from pathlib import Path
from .run import run


def main():
    parser = argparse.ArgumentParser(description='Run deterministic offline software diagnostics (no models).')
    parser.add_argument('--config', type=Path, default=Path('configs/pilot.json'))
    parser.add_argument('--output', type=Path, default=Path('artifacts/pilot'))
    args = parser.parse_args()
    rows = run(json.loads(args.config.read_text()), args.output)
    print(f'Wrote {len(rows)} diagnostic evaluations to {args.output.resolve()}')
    print('Mock outputs validate software, not LLM behavior.')


if __name__ == '__main__':
    main()
