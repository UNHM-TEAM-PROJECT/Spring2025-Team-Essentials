#Test cases
import unittest
import re
from chatbot import app, qa, prompt_template, validate_answer

class ChatbotTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize the Flask test client
        cls.client = app.test_client()

    def ask_question(self, question):
        # Format the question using the prompt template and query the QA system
        query = prompt_template.format(question=question)
        generated_text = qa(query)
        return validate_answer(question, generated_text)

    def test_first_sprint_start(self):
        question = "When does the first sprint start?"
        response = self.ask_question(question)
        self.assertIn("Answer:", response)
        # Ensure the response includes a date or a specific timeline
        self.assertRegex(response, r"\b(start|begin|Sprint|week|day|date)\b")

    def test_instructor(self):
        question = "Who is the instructor for the course?"
        response = self.ask_question(question)
        self.assertIn("Answer:", response)
        # Check if the instructor's name is in the response
        self.assertIn("Karen Jin", response)  # Assuming the instructor is Karen Jin

    def test_office_hours(self):
        question = "What are the course office hours?"
        response = self.ask_question(question)
        self.assertIn("Answer:", response)
        # Ensure office hours are mentioned
        self.assertRegex(response, r"\b(AM|PM|hours|Monday|Tuesday)\b")  # Example time patterns

    def test_course_credits(self):
        question = "How many credits is the course?"
        response = self.ask_question(question)
        self.assertIn("Answer:", response)
        # Check for a numerical value for credits (e.g., 3 credits)
        self.assertRegex(response, r"\b4\b")  # Assuming 3 credits

    
    def test_week_3_activities(self):
        question = "What are the activities planned for Week 3?"
        response = self.ask_question(question)
        self.assertIn("Answer:", response)
        # Ensure Week 3 activities are mentioned
        self.assertRegex(response, r"\b(Week 3|activity|project|task|Sprint)\b")

    def test_sprint_count(self):
        question = "How many sprints are there?"
        response = self.ask_question(question)
        self.assertIn("Answer:", response)
        # Check for a numerical value for the number of sprints
        self.assertRegex(response, r"\b\d+\b")  # Ensures a number is provided

    def test_grading_policy(self):
        question = "What is the grading policy?"
        response = self.ask_question(question)
        self.assertIn("Answer:", response)
        # Ensure the grading policy is mentioned
        self.assertRegex(response, r"\b(grade|percentage|A|B|pass|fail)\b")  # Common grading terms

# Run the tests
if __name__ == '__main__':
    unittest.main()
    unittest.main()
