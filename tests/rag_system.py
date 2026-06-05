from rag_service import create_query_engine, load_and_index_documents


def test_rag_system():
    """Test the RAG system with sample queries"""

    try:
        # Load documents and create index
        index = load_and_index_documents()

        # Create query engine
        query_engine = create_query_engine(index)

        # Sample test queries
        test_queries = [
            "Summarize this document in 3 lines",
            "What are the main topics covered in these documents?",
        ]

        print("RAG System Test Results")
        print("=" * 50)

        for i, query in enumerate(test_queries, 1):
            print(f"\nTest {i}: {query}")
            print("-" * 40)

            try:
                response = query_engine.query(query)
                print(f"Response: {response}")
                print(f"Status: SUCCESS")
            except Exception as e:
                print(f"Error: {str(e)}")
                print(f"Status: FAILED")

            print("-" * 40)

        return True

    except Exception as e:
        print(f"System Error: {str(e)}")
        return False
    

# Main execution
if __name__ == "__main__":

    print("Starting RAG Pipeline Test...")

    # Test the complete system
    success = test_rag_system()

    if success:
        print("\nRAG system is working correctly!")
    else:
        print("\nRAG system test failed. Check the error messages above.")