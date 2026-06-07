import 'package:flutter_test/flutter_test.dart';

import 'package:frontend/app/app.dart';

void main() {
  testWidgets('renders VersaMed starter shell', (WidgetTester tester) async {
    await tester.pumpWidget(const VersaMedApp());

    expect(find.text('VersaMed'), findsOneWidget);
    expect(find.text('Frontend base is ready'), findsOneWidget);
  });
}
