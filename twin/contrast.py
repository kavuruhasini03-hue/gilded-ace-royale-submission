"""Check text and data-mark contrast against both dark surfaces."""
from pathlib import Path
import re

css = Path(__file__).with_name("style.css").read_text()
palette = dict(re.findall(r"--([a-z0-9]+):(#\w{6})", css))


def luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    lighter, darker = sorted((luminance(a), luminance(b)), reverse=True)
    return (lighter + .05) / (darker + .05)


for background in ("canvas", "baize", "panel"):
    for foreground in ("ivory", "smoke", "gold", "purple", "cyan", "coral", "brass", "bone", "jade"):
        score = contrast(palette[background], palette[foreground])
        assert score >= 4.5, (background, foreground, score)
        print(f"{foreground} on {background}: {score:.2f}:1")
assert contrast("#55736a", palette["canvas"]) >= 3
for foreground, background in [("headline","felt"),("headline","felt2"),("cardink","bone"),("gold2","cardback")]:
    assert contrast(palette[foreground],palette[background]) >= 4.5, (foreground,background)
assert contrast("#2a1a00","#b88a24") >= 4.5
print("PASS: palette text, suit chips, opaque chart marks and control borders.")
