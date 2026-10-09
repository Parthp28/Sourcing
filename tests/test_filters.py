import unittest

from job_pulse.filters import Decision, classify_job, classify_location, classify_role


class RoleClassificationTests(unittest.TestCase):
    def test_target_role_families_are_kept(self):
        for title in (
            "Software Engineer, New Grad",
            "Backend Engineering Intern",
            "Data Engineer I",
            "Machine Learning Engineer",
            "AI Engineer Intern",
        ):
            with self.subTest(title=title):
                self.assertNotEqual(classify_role(title).decision, Decision.INELIGIBLE)

    def test_senior_role_is_rejected(self):
        self.assertEqual(
            classify_role("Senior Software Engineer").decision,
            Decision.INELIGIBLE,
        )

    def test_level_two_role_is_reviewed(self):
        self.assertEqual(
            classify_role("Software Engineer II").decision,
            Decision.REVIEW,
        )


class LocationClassificationTests(unittest.TestCase):
    def test_explicit_us_locations_are_accepted(self):
        for location in (
            "San Francisco, CA",
            "New York, New York, United States",
            "Remote - US Only",
        ):
            with self.subTest(location=location):
                self.assertEqual(classify_location(location).decision, Decision.APPLY)

    def test_foreign_locations_are_rejected(self):
        for location in (
            "Budapest, Hungary",
            "Stockholm, Sweden",
            "Bengaluru, India",
            "Berlin, DE",
        ):
            with self.subTest(location=location):
                self.assertEqual(classify_location(location).decision, Decision.INELIGIBLE)

    def test_plain_remote_is_reviewed(self):
        self.assertEqual(classify_location("Remote").decision, Decision.REVIEW)


class CombinedClassificationTests(unittest.TestCase):
    def test_two_year_requirement_is_reviewed(self):
        result = classify_job(
            "Software Engineer",
            "Seattle, WA",
            "Requires 2+ years of software development experience.",
        )
        self.assertEqual(result.decision, Decision.REVIEW)

    def test_clearance_requirement_is_rejected(self):
        result = classify_job(
            "Software Engineer",
            "Austin, TX",
            "Applicants must be a U.S. citizen and hold an active security clearance.",
        )
        self.assertEqual(result.decision, Decision.INELIGIBLE)


if __name__ == "__main__":
    unittest.main()
