// Lightweight dashboard charts (no chart package needed).
// Colour rule: a single series uses kSeries; follow-up states use the fixed status colours.
import 'dart:math' as math;

import 'package:flutter/material.dart';

const kSeries = Color(0xFF2A78D6);
const kSeriesTrack = Color(0xFFCDE2FB);
const kGood = Color(0xFF0CA30C);
const kWarning = Color(0xFFFAB219);
const kCritical = Color(0xFFD03B3B);
const kNeutral = Color(0xFFC3C2B7);
const kInk = Color(0xFF0F172A);
const kMuted = Color(0xFF64748B);
const kBorder = Color(0xFFE2E8F0);
const kTrack = Color(0xFFF1F5F9);
const _kGrid = Color(0xFFE8E7E1);
const _kBaseline = Color(0xFFC3C2B7);

/// One column in the chart: short axis label, long label for the tooltip, value.
class ChartPoint {
  const ChartPoint(this.label, this.long, this.value);
  final String label, long;
  final int value;
}

/// Single-series column chart. Tap or drag across it to read a day's value.
class ColumnChart extends StatefulWidget {
  const ColumnChart({super.key, required this.points, this.height = 200, this.unit = 'visits', this.unitOne = 'visit'});
  final List<ChartPoint> points;
  final double height;
  final String unit, unitOne;
  @override
  State<ColumnChart> createState() => _ColumnChartState();
}

class _ColumnChartState extends State<ColumnChart> {
  int? _selected;

  void _pick(Offset p, double width, {bool toggle = false}) {
    final n = widget.points.length;
    if (n == 0) return;
    final band = (width - _Geo.left) / n;
    final i = ((p.dx - _Geo.left) / band).floor().clamp(0, n - 1);
    setState(() => _selected = (toggle && _selected == i) ? null : i);
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, c) {
      final w = c.maxWidth;
      final size = Size(w, widget.height);
      final geo = _Geo(widget.points, size);
      final sel = _selected;
      return GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (d) => _pick(d.localPosition, w, toggle: true),
        onHorizontalDragUpdate: (d) => _pick(d.localPosition, w),
        child: SizedBox(
          width: w,
          height: widget.height,
          child: Stack(clipBehavior: Clip.none, children: [
            CustomPaint(size: size, painter: _ColumnPainter(widget.points, sel, geo)),
            if (sel != null && sel < widget.points.length)
              Positioned(
                top: -6,
                left: (geo.cx(sel) - 70).clamp(0.0, math.max(0.0, w - 140)).toDouble(),
                width: 140,
                child: IgnorePointer(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                    decoration: BoxDecoration(
                      color: kInk,
                      borderRadius: BorderRadius.circular(10),
                      boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 12, offset: Offset(0, 4))],
                    ),
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Text('${widget.points[sel].value} ${widget.points[sel].value == 1 ? widget.unitOne : widget.unit}',
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 13)),
                      Text(widget.points[sel].long,
                          maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Color(0xFFCBD5E1), fontSize: 11)),
                    ]),
                  ),
                ),
              ),
          ]),
        ),
      );
    });
  }
}

/// Shared geometry for painter and tooltip.
class _Geo {
  static const left = 28.0, bottom = 24.0, top = 24.0;
  _Geo(this.points, this.size) {
    final maxV = points.fold<int>(0, (m, p) => math.max(m, p.value));
    step = _niceStep(maxV);
    axisTop = maxV <= 0 ? 4 : (maxV / step).ceil() * step;
    plotBottom = size.height - bottom;
    band = points.isEmpty ? 0 : (size.width - left) / points.length;
    barW = math.min(18.0, band * 0.62);
  }
  final List<ChartPoint> points;
  final Size size;
  late final int step, axisTop;
  late final double plotBottom, band, barW;

  double cx(int i) => left + band * i + band / 2;
  double y(num v) => plotBottom - (v / axisTop) * (plotBottom - top);
  List<int> get ticks => [for (var t = 0; t <= axisTop; t += step) t];

  static int _niceStep(int max) {
    if (max <= 4) return 1;
    final raw = max / 4;
    final mag = math.pow(10, (math.log(raw) / math.ln10).floor()).toDouble();
    for (final m in const [1.0, 2.0, 2.5, 5.0, 10.0]) {
      if (m * mag >= raw) return math.max(1, (m * mag).ceil());
    }
    return (10 * mag).ceil();
  }
}

class _ColumnPainter extends CustomPainter {
  _ColumnPainter(this.points, this.selected, this.geo);
  final List<ChartPoint> points;
  final int? selected;
  final _Geo geo;

  @override
  void paint(Canvas canvas, Size size) {
    // hairline grid + y ticks
    for (final t in geo.ticks) {
      final y = geo.y(t);
      canvas.drawLine(Offset(_Geo.left, y), Offset(size.width, y), Paint()
        ..color = t == 0 ? _kBaseline : _kGrid
        ..strokeWidth = 1);
      _text(canvas, '$t', Offset(_Geo.left - 6, y), align: TextAlign.right);
    }
    if (points.isEmpty) return;

    final n = points.length;
    final every = geo.band < 24 ? 3 : (geo.band < 36 ? 2 : 1);
    final maxV = points.fold<int>(0, (m, p) => math.max(m, p.value));
    final maxIdx = maxV > 0 ? points.indexWhere((p) => p.value == maxV) : -1;

    for (var i = 0; i < n; i++) {
      final p = points[i];
      final cx = geo.cx(i);
      if (p.value > 0) {
        final h = math.max(2.0, geo.plotBottom - geo.y(p.value));
        final r = RRect.fromRectAndCorners(
          Rect.fromLTWH(cx - geo.barW / 2, geo.plotBottom - h, geo.barW, h),
          topLeft: const Radius.circular(4),
          topRight: const Radius.circular(4),
        );
        final dim = selected != null && selected != i;
        canvas.drawRRect(r, Paint()..color = dim ? kSeries.withAlpha(110) : kSeries);
        // label only the peak and today, and only when nothing is selected
        if (selected == null && (i == maxIdx || i == n - 1)) {
          _text(canvas, '${p.value}', Offset(cx, geo.plotBottom - h - 9), color: kInk, weight: FontWeight.w700, size: 11);
        }
      }
      if (i % every == (n - 1) % every) {
        final last = i == n - 1;
        _text(canvas, p.label, Offset(cx, size.height - 9),
            color: last ? kInk : kMuted, weight: last ? FontWeight.w700 : FontWeight.w400);
      }
    }
  }

  void _text(Canvas c, String s, Offset at,
      {Color color = kMuted, double size = 10, FontWeight weight = FontWeight.w400, TextAlign align = TextAlign.center}) {
    final tp = TextPainter(
      text: TextSpan(text: s, style: TextStyle(color: color, fontSize: size, fontWeight: weight)),
      textDirection: TextDirection.ltr,
    )..layout();
    var dx = at.dx;
    if (align == TextAlign.center) dx -= tp.width / 2;
    if (align == TextAlign.right) dx -= tp.width;
    tp.paint(c, Offset(dx, at.dy - tp.height / 2));
  }

  @override
  bool shouldRepaint(covariant _ColumnPainter old) => old.selected != selected || old.points != points || old.geo.size != geo.size;
}

/// Horizontal bars for comparing categories (one colour).
class HBarItem {
  const HBarItem(this.label, this.value, {this.trailing});
  final String label;
  final int value;
  final Widget? trailing;
}

class HBarList extends StatelessWidget {
  const HBarList({super.key, required this.items});
  final List<HBarItem> items;
  @override
  Widget build(BuildContext context) {
    final max = items.fold<int>(1, (m, x) => math.max(m, x.value));
    return Column(children: [
      for (final it in items)
        Padding(
          padding: const EdgeInsets.only(bottom: 14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                child: Text(it.label,
                    maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w500, color: Color(0xFF334155))),
              ),
              if (it.trailing != null) ...[it.trailing!, const SizedBox(width: 8)],
              Text('${it.value}', style: const TextStyle(fontWeight: FontWeight.w700, color: kInk)),
            ]),
            const SizedBox(height: 6),
            Container(
              width: double.infinity,
              height: 8,
              decoration: BoxDecoration(color: kTrack, borderRadius: BorderRadius.circular(99)),
              child: FractionallySizedBox(
                alignment: Alignment.centerLeft,
                widthFactor: it.value / max,
                child: DecoratedBox(decoration: BoxDecoration(color: kSeries, borderRadius: BorderRadius.circular(99))),
              ),
            ),
          ]),
        ),
    ]);
  }
}

/// Part-to-whole: one segmented bar with a 2px gap between segments.
class StackedSegment {
  const StackedSegment(this.label, this.value, this.color, this.icon);
  final String label;
  final int value;
  final Color color;
  final IconData icon;
}

class StackedBar extends StatelessWidget {
  const StackedBar({super.key, required this.segments});
  final List<StackedSegment> segments;
  @override
  Widget build(BuildContext context) {
    final total = segments.fold<int>(0, (s, x) => s + x.value);
    final shown = segments.where((s) => s.value > 0).toList();
    return Column(children: [
      ClipRRect(
        borderRadius: BorderRadius.circular(99),
        child: SizedBox(
          height: 12,
          child: total == 0
              ? const ColoredBox(color: kTrack, child: SizedBox.expand())
              : Row(children: [
                  for (var i = 0; i < shown.length; i++) ...[
                    if (i > 0) const SizedBox(width: 2),
                    Expanded(flex: shown[i].value, child: ColoredBox(color: shown[i].color)),
                  ],
                ]),
        ),
      ),
      const SizedBox(height: 14),
      for (final s in segments)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 5),
          child: Row(children: [
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(color: s.color.withAlpha(36), borderRadius: BorderRadius.circular(8)),
              child: Icon(s.icon, size: 16, color: s.color == kNeutral ? kMuted : s.color),
            ),
            const SizedBox(width: 12),
            Expanded(child: Text(s.label, style: const TextStyle(color: Color(0xFF334155)))),
            Text('${s.value}', style: const TextStyle(fontWeight: FontWeight.w700, color: kInk)),
            SizedBox(
              width: 48,
              child: Text('${total == 0 ? 0 : (s.value * 100 / total).round()}%',
                  textAlign: TextAlign.right, style: const TextStyle(fontSize: 12, color: kMuted)),
            ),
          ]),
        ),
    ]);
  }
}

/// Small trend line; the latest point is marked with a dot.
class Sparkline extends StatelessWidget {
  const Sparkline({super.key, required this.values, this.color = Colors.white, this.width = 96, this.height = 34});
  final List<int> values;
  final Color color;
  final double width, height;
  @override
  Widget build(BuildContext context) =>
      values.length < 2 ? SizedBox(width: width, height: height) : CustomPaint(size: Size(width, height), painter: _SparkPainter(values, color));
}

class _SparkPainter extends CustomPainter {
  _SparkPainter(this.values, this.color);
  final List<int> values;
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    final max = math.max(1, values.reduce(math.max));
    Offset pt(int i) => Offset(3 + i / (values.length - 1) * (size.width - 6), size.height - 4 - values[i] / max * (size.height - 8));
    final path = Path()..moveTo(pt(0).dx, pt(0).dy);
    for (var i = 1; i < values.length; i++) {
      path.lineTo(pt(i).dx, pt(i).dy);
    }
    canvas.drawPath(path, Paint()
      ..color = color.withAlpha(150)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeJoin = StrokeJoin.round
      ..strokeCap = StrokeCap.round);
    final last = pt(values.length - 1);
    canvas.drawCircle(last, 4, Paint()..color = color);
  }

  @override
  bool shouldRepaint(covariant _SparkPainter old) => old.values != values || old.color != color;
}

/// Progress against a total; the track is a lighter step of the same blue.
class Meter extends StatelessWidget {
  const Meter({super.key, required this.value, required this.total});
  final int value, total;
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        height: 10,
        decoration: BoxDecoration(color: kSeriesTrack, borderRadius: BorderRadius.circular(99)),
        child: FractionallySizedBox(
          alignment: Alignment.centerLeft,
          widthFactor: total == 0 ? 0 : (value / total).clamp(0.0, 1.0),
          child: DecoratedBox(decoration: BoxDecoration(color: kSeries, borderRadius: BorderRadius.circular(99))),
        ),
      );
}
