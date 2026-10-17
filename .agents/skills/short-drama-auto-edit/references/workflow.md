# 工具和剪辑计划

## 依赖与执行

附带脚本使用Python标准库；视频读取和渲染需要FFmpeg及FFprobe。可通过环境变量 `FFMPEG_BINARY`、`FFPROBE_BINARY` 指定程序绝对路径，或放入PATH。doctor仅检查可发现状态，不代表模型已下载或工具已成功处理视频。

镜头检测与视频观看使用当前环境可用的工具；本技能不指定付费服务，也不自动上传素材。语音转写、字幕识别和OCR已恢复，用于内部分析。优先使用可靠原字幕或已有工具，结合画面核对识别结果，不把识别文字自动写入成片。

以下命令中的素材、计划和输出路径替换为真实绝对路径。脚本路径相对技能目录；输出目录须使用新的工作目录，不覆盖原片。

```text
python scripts/drama_edit.py doctor
python scripts/drama_edit.py inspect --input EPISODE.mp4
python scripts/drama_edit.py extract --input EPISODE.mp4 --out NEW_ANALYSIS_DIR --interval 5
python scripts/drama_edit.py validate --plan EDIT_PLAN.json
python scripts/drama_edit.py render --plan EDIT_PLAN.json --out NEW_RENDER_DIR
```

extract输出媒体信息、定时JPEG及有音轨时的16kHz单声道WAV，可供内部语音转写使用。序号000001的帧约对应0秒，后续按interval递增；这是粗略浏览索引，不能用于帧精确的剪切判断。对候选爆点另行提取精确区间进行观察。长素材按集处理，避免一次提取全部高清帧。

render先探测源文件并验证区间，然后逐段重编码统一尺寸和音频参数，再拼接。没有音轨的片段补同长度静音。它保留黑边，避免自动裁掉剧情信息；只保留画面内的原字幕，不提供添加字幕功能，不自动添加配乐。不得追加字幕烧录、drawtext或其他文字叠加处理。原素材无字幕的区间保持无字幕。OCR与转写只用于内部分析，不参与文字叠加。此脚本只映射音视频轨，原片若有独立字幕轨，应改用能同步保留原轨的工具，不得静默丢弃。输出 `finished.mp4`、`render-report.json` 和中间分段。渲染目录必须不存在；失败后保留现场，在新目录重试。不要递归删除素材或工作目录来重试。

## 计划结构

JSON使用UTF-8；时间为原片的秒数（可带小数），区间按开始含、结束不含理解。所有源文件必须是本地绝对路径。下面只说明结构，实际文件和时间必须来自素材；不是可直接执行的成片方案。

```json
{
  "target_min": 240,
  "target_max": 300,
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "clips": [
    {
      "source": "C:/素材/第1集.mp4",
      "start": 10.2,
      "end": 130.2,
      "reason": "冲突建立并升级；实际执行时补充具体对白和画面证据"
    },
    {
      "source": "C:/素材/第2集.mp4",
      "start": 0,
      "end": 130,
      "reason": "前一段结果引出新的对抗和悬念；以实际剧情为准"
    }
  ]
}
```

校验会拒绝缺失源文件、非有限数值、非法时间、超出原片、缺少理由、非偶数尺寸和目标时长不符。同源区间重叠作为警告，需人工判断预告回放是否合理。validate需要FFprobe；无依赖时可用Python导入 `validate_plan(plan, durations)` 对已知时长验证计划结构，不能因此声称源文件已解码。

## 成片质量报告

记录：实际时长/尺寸、解码检查、分析覆盖范围、开头爆点证据、冲突推进顺序、每处接缝检查、字幕/声音处理、可疑黑场或静音区间、未完成检查。脚本的render-report只报告媒体技术结果，不代替剧情、字幕和听感检查。发现内容问题后修改计划重新渲染，保留对应计划版本。
