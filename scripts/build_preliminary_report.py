"""Rebuild the dated report addendum from saved diagnostics and failed live pilot."""
import argparse
import io
import json
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from pypdf import PdfReader, PdfWriter

ROOT=Path(__file__).resolve().parents[1]

def build(source,output):
    offline=json.loads((ROOT/'artifacts/transformations/summary.json').read_text())
    live=ROOT/'artifacts/real-vision-gemini'
    status=json.loads((live/'run_status.json').read_text())
    extraction=json.loads((live/'extraction_summary.json').read_text())
    # This status addendum must not silently overwrite itself with a success narrative.
    if status['status']!='stopped' or status['valid_outputs']!=0:
        raise ValueError('Live status changed; review the report narrative before rebuilding')
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyCustom',fontName='Helvetica',fontSize=9.5,leading=12.5,spaceAfter=6,textColor=colors.HexColor('#253346')))
    styles.add(ParagraphStyle(name='SmallCustom',fontName='Helvetica',fontSize=8,leading=11,spaceAfter=6))
    styles['Title'].fontSize=21;styles['Title'].leading=25;styles['Title'].alignment=TA_LEFT
    styles['Heading2'].fontSize=13;styles['Heading2'].textColor=colors.HexColor('#18556a')
    story=[]
    def para(text,style='BodyCustom'):story.append(Paragraph(text,styles[style]))
    def table(data,widths):
        t=Table(data,colWidths=widths,hAlign='LEFT',repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#183b4b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
          ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,1),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),9),
          ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#eff5f7'),colors.white]),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
          ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#b7c8ce'))]))
        story.append(t);story.append(Spacer(1,10))
    para('Preliminary implementation results','Title')
    para('ADDENDUM | October 30, 2026 | Software diagnostics and live-pilot status','SmallCustom')
    para('<b>Scope update.</b> This dated addendum supplements the original report. Its statements in Sections 4.2 and 6 that no experiments were executed describe the October 28 report. Since then, offline software diagnostics and an incomplete live API attempt were executed. No successful real-vision comparison is reported here.')
    para('A. Verified offline transformation diagnostics','Heading2')
    para('Ten balanced synthetic base instances, six paired conditions, four programmed methods: 240 evaluations. Sensor reliability is 0.75, prior 0.5, and approval threshold 0.90. Workers use fixture observations, not image perception. These results verify implementation behavior; they are not measured LLM effectiveness.')
    data=[['Mean absolute oracle error','Naive','Hash','Lineage','Perceptual']]
    names={'single_raster':'Single raster','exact_replay':'Exact replay','resized_jpeg':'Resize + JPEG','cropped_replay':'Crop replay','cross_modal':'Synthetic cross-modal','independent_raster':'Independent acquisitions'}
    for c,label in names.items():
        data.append([label]+[f"{next(s['mean_absolute_confidence_error'] for s in offline if s['condition']==c and s['method']==m):.4f}" for m in ('naive','hash','lineage','perceptual')])
    table(data,[198,65,65,65,83])
    para('Each cell averages 10 valid software outputs. Naive replay prematurely approves 4/10 oracle-ineligible cases. Hashing also approves 4/10 in each transformed/cross-modal replay condition because bytes differ. Trusted lineage has zero oracle error in these fixtures. In the independent condition, naive and lineage retain 2/2 oracle-supported approvals; hash and perceptual matching retain 0/2 after merging equal-looking independent observations.')
    para('B. Verification and interpretation','Heading2')
    para('The original pilot and transformation commands run. Artifact manifests verify; the original pilot outputs are unchanged. Regression tests cover ancestry, actual-byte hashes, extraction boundaries, cache replay/integrity, quota stopping, and failure denominators. Transformed glyphs are readable in the contact sheet, and the known-geometry signal checks pass.')
    para('Calibration roots are separate from evaluation, but appearance templates overlap. The perceptual matcher is image-only and crop-sensitive. Acquisition independence is stipulated by the synthetic generator; root IDs alone do not establish independence in real settings. These diagnostic outcomes must not be used as evidence that an LLM defense works.')
    para('Source: artifacts/transformations/summary.json and reviewed provenance/signal checks. Values are regenerated from saved outputs by scripts/build_preliminary_report.py.','SmallCustom')
    story.append(PageBreak())
    para('Real-vision pilot: incomplete','Title')
    para('GEMINI 3.8 FLASH | Billing-disabled free tier | $0 cap | No paid fallback','SmallCustom')
    para('C. Implemented model pipeline','Heading2')
    para('The opt-in adapter sends actual PNG/JPEG bytes to Gemini and validates structured observations. A separate image-to-record call can create the cross-modal derivative; trusted code preserves its parent and acquisition root. Naive, instruction-only, and trusted-lineage methods share cached worker reports and the same aggregator model. Non-null probabilities must come from model responses with valid evidence citations. Ground truth and oracle values remain evaluator-only.')
    para('D. Observed execution outcome','Heading2')
    table([['Two-instance stage','Observed outcome'],['Scheduled method-condition rows',str(status['scheduled_evaluations'])],['Attempted aggregation evaluations',str(status['attempted_evaluations'])],['Valid aggregation outputs',str(status['valid_outputs'])],['Vision extraction calls / resolved',f"{extraction['attempted']} / {extraction['resolved']}"],['Completed base-instance comparisons','0'],['Ten-instance live stage','Not started'],['Run status','Stopped: HTTP 503 (high demand)']],[245,231])
    para('The first image request timed out after 90 seconds and was not resent. An authenticated read-only model lookup succeeded. After manual review, remaining requests continued: one aggregator response failed citation validation, and the next received HTTP 503 indicating high demand. Execution stopped. Raw outcomes, model settings, timing, usage when available, and failure details are preserved. A separate sandbox connectivity failure is excluded from these live-stage counts.')
    para('<b>No empirical vision accuracy, valid aggregation comparison, or efficacy interval is available.</b> The 36 scheduled rows remain explicit: two attempted failures and 34 not-attempted rows. Null probabilities and failed requests are not converted into successful abstentions. A zero approval count in this incomplete run is not evidence of safety or improved calibration.')
    para('E. Next experimental step','Heading2')
    para('When free-tier service is available, review the stopped run and plan an explicitly documented continuation or new frozen replicate. Preserve timeout outcomes rather than silently retrying or dropping them. Complete and inspect the two-instance stage before ten. Only then report paired whole-base bootstrap intervals, extraction accuracy, confidence inflation, Brier score, premature/incorrect approvals, retention, and coverage. Small synthetic samples cannot establish natural-image performance or general LLM defense effectiveness.')
    para('AI usage update: Codex assisted with implementation, tests, API execution, diagnostic analysis, and this addendum. The original report is retained unchanged; no successful live result is implied by its prospective methodology.','SmallCustom')
    para('Evidence: artifacts/real-vision-gemini/{run_status.json,results.jsonl,extraction_summary.json,cache/}; protocol: docs/real-vision-pilot.md. Official model and free-tier references: ai.google.dev/gemini-api/docs/models/gemini-3.8-flash and ai.google.dev/gemini-api/docs/pricing (checked October 30, 2026).','SmallCustom')
    buf=io.BytesIO()
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#607080'))
        canvas.drawString(50,28,'CS 562 | Dated preliminary addendum | No successful real-vision comparison')
        canvas.drawRightString(562,28,str(9+doc.page))
    SimpleDocTemplate(buf,pagesize=(612,792),leftMargin=50,rightMargin=50,topMargin=35,bottomMargin=40).build(story,onFirstPage=footer,onLaterPages=footer)
    add=PdfReader(buf)
    if len(add.pages)!=2:raise ValueError(f'Unexpected addendum pagination: {len(add.pages)}')
    writer=PdfWriter();writer.append(PdfReader(source));writer.append(add)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb') as stream:writer.write(stream)
    print(output)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',default='/Users/aditi/Downloads/562.pdf');p.add_argument('--output',default=str(ROOT/'output/pdf/562-with-preliminary-status.pdf'));a=p.parse_args();build(a.source,a.output)
