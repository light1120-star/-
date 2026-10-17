"""Local media helpers; editorial decisions are made by the skill, not this script."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys


def binary(name):
    value = os.environ.get(name.upper() + '_BINARY', name)
    found = shutil.which(value)
    if not found:
        raise ValueError(f'Missing {name}; configure {name.upper()}_BINARY or PATH')
    return found


def run(args):
    result = subprocess.run(args, capture_output=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise ValueError(result.stderr[-6000:] or f'Command failed: {args[0]}')
    return result.stdout


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def probe(path):
    data = json.loads(run([binary('ffprobe'), '-v', 'error', '-show_format',
                           '-show_streams', '-of', 'json', str(path)]))
    if not any(s['codec_type'] == 'video' for s in data['streams']):
        raise ValueError(f'No video stream: {path}')
    return data


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)


def validate_plan(plan, durations):
    low = number(plan.get('target_min', 240), 'target_min')
    high = number(plan.get('target_max', 300), 'target_max')
    if not 0 < low <= high:
        raise ValueError('Invalid target range')
    for key, default in [('width', 1080), ('height', 1920)]:
        value = plan.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 2 or value % 2:
            raise ValueError(f'{key} must be a positive even integer')
    if not 1 <= number(plan.get('fps', 30), 'fps') <= 120:
        raise ValueError('fps must be between 1 and 120')
    clips = plan.get('clips')
    if not isinstance(clips, list) or not clips:
        raise ValueError('clips must be a nonempty list')
    total, seen, warnings = 0.0, {}, []
    for index, clip in enumerate(clips, 1):
        source = clip['source']
        if not isinstance(source, str) or not Path(source).is_absolute() or not Path(source).is_file():
            raise ValueError(f'Clip {index}: source must be an existing absolute file path')
        start, end = number(clip['start'], 'start'), number(clip['end'], 'end')
        duration = number(durations[source], 'source duration')
        if not 0 <= start < end <= duration:
            raise ValueError(f'Clip {index}: interval outside source duration {duration}')
        if not isinstance(clip.get('reason'), str) or not clip['reason'].strip():
            raise ValueError(f'Clip {index}: missing editorial reason')
        key = os.path.normcase(str(Path(source).resolve()))
        for old_start, old_end in seen.get(key, []):
            if max(start, old_start) < min(end, old_end):
                warnings.append(f'Clip {index}: overlapping source footage; review repetition')
                break
        seen.setdefault(key, []).append((start, end))
        total += end - start
    if total < low - 1e-6 or total > high + 1e-6:
        raise ValueError(f'Planned duration {total:.3f}s outside {low}–{high}s')
    return {'planned_seconds': total, 'warnings': warnings}


def load_plan(path):
    plan = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    sources = {clip['source'] for clip in plan['clips']}
    for source in sources:
        if not Path(source).is_absolute() or not Path(source).is_file():
            raise ValueError(f'Expected existing absolute local source: {source}')
    media = {source: probe(source) for source in sources}
    durations = {source: float(info['format']['duration']) for source, info in media.items()}
    return plan, media, validate_plan(plan, durations)


def new_directory(path):
    target = Path(path).resolve()
    target.mkdir(parents=True, exist_ok=False)
    return target


def extract(args):
    if not math.isfinite(args.interval) or args.interval <= 0:
        raise ValueError('interval must be positive and finite')
    source = Path(args.input).resolve(strict=True)
    info = probe(source)
    ffmpeg = binary('ffmpeg')
    out = new_directory(args.out)
    write_json(out / 'media.json', info)
    run([ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', str(source), '-map', '0:v:0',
         '-vf', f'fps=1/{args.interval},scale=640:-2', '-q:v', '3', str(out / 'frame-%06d.jpg')])
    if any(s['codec_type'] == 'audio' for s in info['streams']):
        run([ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', str(source), '-map', '0:a:0',
             '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(out / 'audio.wav')])
    return {'output': str(out), 'frame_interval_seconds': args.interval,
            'note': 'Coarse visual index only; no transcription or editorial analysis performed'}


def render(args):
    plan, media, report = load_plan(args.plan)
    ffmpeg = binary('ffmpeg')
    out = new_directory(args.out)
    width, height, fps = plan.get('width', 1080), plan.get('height', 1920), plan.get('fps', 30)
    names = []
    for index, clip in enumerate(plan['clips']):
        name = f'part-{index:04d}.mp4'
        names.append(name)
        duration = clip['end'] - clip['start']
        command = [ffmpeg, '-nostdin', '-v', 'error', '-n', '-ss', str(clip['start']),
                   '-i', clip['source']]
        has_audio = any(s['codec_type'] == 'audio' for s in media[clip['source']]['streams'])
        if not has_audio:
            command += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
        vf = (f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,'
              f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},setpts=PTS-STARTPTS')
        command += ['-map', '0:v:0', '-map', '0:a:0' if has_audio else '1:a:0',
                    '-t', str(duration), '-vf', vf,
                    '-af', 'asetpts=PTS-STARTPTS,aresample=48000:async=1:first_pts=0,apad',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', str(out / name)]
        run(command)
    listing = out / 'concat.txt'
    listing.write_text(''.join(f"file '{name}'\n" for name in names), encoding='utf-8')
    finished = out / 'finished.mp4'
    run([ffmpeg, '-nostdin', '-v', 'error', '-n', '-f', 'concat', '-safe', '1',
         '-i', str(listing), '-c', 'copy', '-movflags', '+faststart', str(finished)])
    actual = probe(finished)
    seconds = float(actual['format']['duration'])
    run([ffmpeg, '-nostdin', '-v', 'error', '-xerror', '-i', str(finished), '-f', 'null', '-'])
    report.update({'actual_seconds': seconds, 'decode_passed': True,
                   'duration_passed': plan.get('target_min', 240) <= seconds <= plan.get('target_max', 300),
                   'output': str(finished), 'editorial_review': 'not performed by script',
                   'subtitle_and_listening_review': 'not performed by script'})
    write_json(out / 'render-report.json', report)
    if not report['duration_passed']:
        raise ValueError(f'Actual duration outside target; inspect {out / "render-report.json"}')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    item = sub.add_parser('inspect')
    item.add_argument('--input', required=True)
    item = sub.add_parser('extract')
    item.add_argument('--input', required=True)
    item.add_argument('--out', required=True)
    item.add_argument('--interval', type=float, default=5)
    for name in ('validate', 'render'):
        item = sub.add_parser(name)
        item.add_argument('--plan', required=True)
        if name == 'render':
            item.add_argument('--out', required=True)
    args = parser.parse_args()
    if args.command == 'doctor':
        result = {'python': sys.executable, 'binaries': {}, 'optional_modules': {}}
        for name in ('ffmpeg', 'ffprobe'):
            try:
                result['binaries'][name] = binary(name)
            except ValueError:
                result['binaries'][name] = None
        for name in ('faster_whisper', 'whisper', 'cv2', 'scenedetect', 'paddleocr', 'rapidocr_onnxruntime'):
            result['optional_modules'][name] = importlib.util.find_spec(name) is not None
    elif args.command == 'inspect':
        result = probe(Path(args.input).resolve(strict=True))
    elif args.command == 'extract':
        result = extract(args)
    elif args.command == 'validate':
        result = load_plan(args.plan)[2]
    else:
        result = render(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
