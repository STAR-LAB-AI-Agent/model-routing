"""Render the editable Markdown report as a typeset Chinese PDF.

pip install -r requirements-artifacts.txt
python scripts/build_report.py [--font /path/to/chinese-font.ttf]
The supplied PDF is built with the Windows SimSun font; bring a licensed CJK
TrueType font for other OSes. This script changes only report identity lines
and writes deliverables/实验报告.pdf.
"""
import argparse
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable

ROOT = Path(__file__).resolve().parents[1]


class Architecture(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = 170*mm, 58*mm

    def draw(self):
        c = self.canv
        c.setFont("CJK", 9)
        boxes = [(0,100,96,"自然语言任务"),(120,100,96,"nanobot Agent"),(240,100,96,"SKILL.md"),
                 (0,30,96,"本地网页 Demo"),(120,30,96,"Script / Service"),(240,30,96,"LiteLLM"),(360,30,108,"模型结果与审计")]
        for x,y,w,label in boxes:
            c.setFillColor(colors.HexColor("#F1F5F2"));c.setStrokeColor(colors.HexColor("#A9BBB0"))
            c.roundRect(x,y,w,34,5,stroke=1,fill=1)
            c.setFillColor(colors.HexColor("#173C32"));c.drawCentredString(x+w/2,y+13,label)
        c.setStrokeColor(colors.HexColor("#608573"))
        for x1,y1,x2,y2 in [(96,117,120,117),(216,117,240,117),(96,47,120,47),(216,47,240,47),(336,47,360,47),(288,100,168,64)]:
            c.line(x1,y1,x2,y2)
        c.setFont("CJK",8);c.setFillColor(colors.HexColor("#607269"))
        c.drawString(0,4,"网页与 CLI 共用核心服务；Agent 通过 Skill 调用独立 Script")


def build(font):
    pdfmetrics.registerFont(TTFont("CJK", str(font), subfontIndex=0))
    identity=json.loads((ROOT/"docs/student-info.json").read_text(encoding="utf-8"))
    source=ROOT/"docs/experiment-report.md"
    content=source.read_text(encoding="utf-8")
    for title,key in [("姓名","name"),("学号","student_id"),("班级","class"),("组员","team_members")]:
        content=re.sub(rf"^{title}：.*$",lambda _:f"{title}：{identity[key]}",content,flags=re.M)
    source.write_text(content,encoding="utf-8")
    body=ParagraphStyle("Body",fontName="CJK",fontSize=10.5,leading=18,spaceAfter=9,wordWrap="CJK",textColor=colors.HexColor("#202720"))
    title=ParagraphStyle("Title",parent=body,fontSize=24,leading=32,spaceAfter=22,textColor=colors.black)
    heading=ParagraphStyle("Heading",parent=body,fontSize=16,leading=24,spaceBefore=8,spaceAfter=13,keepWithNext=True,textColor=colors.black)
    small=ParagraphStyle("Small",parent=body,fontSize=9,leading=15,spaceAfter=5)
    cell=ParagraphStyle("Cell",parent=body,fontSize=9,leading=14,spaceAfter=0)
    story=[];lines=content.splitlines();i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line: i+=1;continue
        if line=="<!-- pagebreak -->": story.append(PageBreak())
        elif line=="<!-- architecture -->": story.extend([Architecture(),Spacer(1,9)])
        elif line.startswith("# "): story.append(Paragraph(escape(line[2:]),title))
        elif line.startswith("## "): story.append(Paragraph(escape(line[3:]),heading))
        elif line.startswith("|"):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith("|"):
                parts=[s.strip() for s in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+",s or "-") for s in parts):
                    rows.append([Paragraph(escape(p),cell) for p in parts])
                i+=1
            widths=([50*mm,120*mm] if len(rows[0])==2 else [46*mm,99*mm,25*mm] if rows[0][0].getPlainText()=="测试组" else [65*mm,52.5*mm,52.5*mm])
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#DCE7E0")),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#CCD7D0")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
            story.extend([table,Spacer(1,12)]);continue
        else:
            text=escape(line)
            text=re.sub(r"(https?://[^\s]+)",r'<link href="\1" color="#244D3C">\1</link>',text)
            story.append(Paragraph(text,small if re.match(r"[1-4]\. https?|[1-4]\. (LiteLLM|nanobot)",line) else body))
        i+=1
    dest=ROOT/"deliverables/实验报告.pdf";dest.parent.mkdir(exist_ok=True)
    def decorate(c,doc):
        c.setFont("CJK",8);c.setFillColor(colors.HexColor("#69776D"))
        c.drawString(20*mm,15*mm,"智能体开发实战 / 第25题")
        c.drawRightString(190*mm,15*mm,f"{doc.page}")
    doc=SimpleDocTemplate(str(dest),pagesize=A4,rightMargin=20*mm,leftMargin=20*mm,topMargin=19*mm,bottomMargin=23*mm,title="AI模型智能路由实验报告",author=identity["name"] if identity["name"]!="待填写" else "")
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
    print(dest)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--font",type=Path,default=Path("C:/Windows/Fonts/simsun.ttc"));a=p.parse_args()
    if not a.font.exists(): p.error("请通过 --font 指定具有中文字符的 TrueType 字体文件。")
    build(a.font)
