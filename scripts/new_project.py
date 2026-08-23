import json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / 'projects'
TEMPLATE = PROJECTS / '_template'


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python scripts/new_project.py video_002')
    project_id = sys.argv[1].strip()
    if not project_id.startswith('video_') or not project_id[6:].isdigit():
        raise SystemExit('Project id must look like video_002')
    dst = PROJECTS / project_id
    if dst.exists():
        raise SystemExit(f'{dst} already exists')
    shutil.copytree(TEMPLATE, dst)
    cfg_path = dst / 'project.json'
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    cfg['id'] = project_id
    cfg['output_name'] = f'{project_id}_FINAL_YOUTUBE.mp4'
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Created {dst}')
    print('Next: add voiceover.mp3, map.json and numbered shots into shots/.')


if __name__ == '__main__':
    main()
