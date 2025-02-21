import os
import requests
import json
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

# Set the OpenAI API key as an environment variable
apikey = os.getenv("OPENAI_API_KEY")

# Predefined test cases for evaluating the chatbot
test_cases = [
    {
        "question": "What are the core parts of the NECHE compliance criteria for syllabi?",
        "expected_answer": "The core parts of NECHE compliance criteria include maintaining high academic quality through measurable learning outcomes, providing clear descriptions and assessment methods for quizzes, exams, and projects, and ensuring transparent communication channels for instructors.",
        "retrieval_context": ["Maintaining high academic quality is a key aspect of NECHE compliance."]
    },
    {
        "question": "How should NECHE-compliant syllabi handle student learning assessments?",
        "expected_answer": "NECHE-compliant syllabi must clearly outline assessment methods such as quizzes, exams, projects, and participation. These assessments should align with the stated learning outcomes and ensure academic rigor.",
        "retrieval_context": [
            "NECHE compliance ensures students receive a quality education with clear evaluation criteria."
        ]
    },
    {
        "question": "What role does accessibility play in NECHE-compliant syllabi?",
        "expected_answer": "Accessibility is a key factor in NECHE compliance, requiring syllabi to provide accommodations for students with disabilities, use universally designed materials, and ensure all course content is accessible to diverse learners.",
        "retrieval_context": [
            "NECHE emphasizes equity, diversity, and inclusion in academic programs."
        ]
    },
    {
        "question": "Why is academic integrity important in NECHE-compliant syllabi?",
        "expected_answer": "Academic integrity ensures that students engage in honest and ethical learning. NECHE-compliant syllabi must include clear policies on plagiarism, cheating, and proper citation of sources.",
        "retrieval_context": [
            "Institutions accredited by NECHE are required to uphold ethical standards in all academic programs."
        ]
    },
    {
        "question": "What should NECHE-compliant syllabi include about faculty qualifications?",
        "expected_answer": "NECHE requires that courses be taught by qualified instructors with expertise in their subject area. Syllabi should include the instructor’s name, credentials, and contact information.",
        "retrieval_context": [
            "NECHE accreditation ensures faculty members are appropriately qualified to teach assigned courses."
        ]
    }
]

# Function to send a question to the chatbot and retrieve its response
def get_chatbot_response(question):
    """
    Sends a question to the chatbot and retrieves the response.
    Args:
        question (str): The question to ask the chatbot.
    Returns:
        str: The chatbot's response or None if an error occurs.
    """
    try:
        response = requests.post('http://127.0.0.1:80/ask', json={"message": question})
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            print(f"Error: Received status code {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error: Unable to reach chatbot API - {e}")
    return None

# Function to evaluate a single test case
def evaluate_test_case(test_case):
    """
    Evaluates a chatbot response against a test case using relevancy and faithfulness metrics.
    Args:
        test_case (dict): A dictionary containing the question, expected answer, and retrieval context.
    Returns:
        dict: Evaluation results including relevancy and faithfulness scores.
    """
    actual_output = get_chatbot_response(test_case["question"])
    if not actual_output:
        print(f"Error fetching chatbot response for question: {test_case['question']}")
        return None

    # Create a test case object for evaluation
    llm_test_case = LLMTestCase(
        input=test_case["question"],
        actual_output=actual_output,
        expected_output=test_case["expected_answer"],
        retrieval_context=test_case["retrieval_context"]
    )

    # Evaluate relevancy and faithfulness of the chatbot response
    relevancy_metric = AnswerRelevancyMetric(threshold=0.9, model="gpt-4-turbo")
    faithfulness_metric = FaithfulnessMetric(threshold=0.9, model="gpt-4-turbo")

    relevancy_metric.measure(llm_test_case)
    faithfulness_metric.measure(llm_test_case)

    # Compile results
    result = {
        "question": test_case["question"],
        "actual_answer": actual_output,
        "expected_answer": test_case["expected_answer"],
        "relevancy_score": relevancy_metric.score,
        "faithfulness_score": faithfulness_metric.score,
        "relevancy_reason": relevancy_metric.reason,
        "faithfulness_reason": faithfulness_metric.reason,
        "retrieval_context": test_case["retrieval_context"]
    }

    # Update the test case with the actual chatbot output
    test_case["actual_answer"] = actual_output
    test_case["relevancy_reason"] = relevancy_metric.reason
    test_case["faithfulness_reason"] = faithfulness_metric.reason
    return result

# Function to evaluate all test cases and save results
def run_tests():
    """
    Runs all test cases, evaluates chatbot performance, and saves results to JSON files.
    """
    results = []
    updated_test_cases = []

    # Evaluate each test case
    for test_case in test_cases:
        result = evaluate_test_case(test_case)
        if result:
            results.append(result)
            updated_test_cases.append(test_case)

    # Save evaluation results to a JSON file
    with open("evaluation_results.json", "w") as results_file:
        json.dump(results, results_file, indent=4)

    # Save updated test cases (with actual outputs) to another JSON file
    with open("updated_test_cases.json", "w") as test_cases_file:
        json.dump(updated_test_cases, test_cases_file, indent=4)

    print("\nEvaluation completed. Results saved to 'evaluation_results.json'.")
    print("Updated test cases saved to 'updated_test_cases.json'.")

# Entry point for the script
if __name__ == "__main__":
    run_tests()
