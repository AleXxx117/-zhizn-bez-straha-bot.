from __future__ import annotations

import unittest

from content import classify, main_menu, pick_response


class ContentTests(unittest.TestCase):
    def test_crisis_is_detected(self) -> None:
        self.assertEqual(classify("Я больше не хочу жить"), "crisis")

    def test_fear_of_death_is_panic_not_crisis(self) -> None:
        self.assertEqual(classify("У меня паника и я боюсь умереть"), "panic")

    def test_single_word_panic_is_detected(self) -> None:
        self.assertEqual(classify("Паника"), "panic")

    def test_medical_red_flag_is_detected(self) -> None:
        self.assertEqual(classify("У меня сильная боль в груди"), "medical_emergency")

    def test_agoraphobia_is_detected(self) -> None:
        self.assertEqual(classify("Мне страшно выйти далеко от дома"), "agoraphobia")

    def test_intrusive_thoughts_are_detected(self) -> None:
        self.assertEqual(classify("Меня мучают навязчивые мысли"), "intrusive")

    def test_response_is_repeatable_for_same_key(self) -> None:
        self.assertEqual(pick_response("anxiety", "x"), pick_response("anxiety", "x"))

    def test_menu_has_buttons(self) -> None:
        self.assertGreaterEqual(len(main_menu()["inline_keyboard"]), 4)


if __name__ == "__main__":
    unittest.main()
