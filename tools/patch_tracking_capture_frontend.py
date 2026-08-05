#!/usr/bin/env python3
"""One-time cleanup for the article tracking capture component."""

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "components" / "intelligence-tracking-capture-controls.tsx"
text = path.read_text(encoding="utf-8")
text = text.replace(
    '''const ENTITY_LABELS: Record<TrackingCaptureEntityType, string> = {\n  company: "公司",\n  person: "人物",\n  topic: "技术／主题",\n};\n\n''',
    "",
    1,
)
text = text.replace(
    '''  useEffect(() => {\n    setEntities(defaultEntityRows(item));\n    setSelectedTrackSlugs(defaultTrackSlugs(item, userTrackingConfig));\n    setNewTrackName("");\n    setStatus("选择对象类型和目标赛道后，即可一次写入追踪配置与文章采集箱。");\n    setStatusKind("neutral");\n  }, [item]);\n\n''',
    "",
    1,
)
path.write_text(text, encoding="utf-8")
