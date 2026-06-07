import 'package:flutter/material.dart';

import 'home_page.dart';

class VersaMedApp extends StatelessWidget {
  const VersaMedApp({super.key});

  @override
  Widget build(BuildContext context) {
    const brandColor = Color(0xFF0F766E);

    return MaterialApp(
      title: 'VersaMed',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: brandColor,
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xFFF4F7F7),
        useMaterial3: true,
      ),
      home: const HomePage(),
    );
  }
}
