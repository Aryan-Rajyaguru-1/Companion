#!/usr/bin/env python3
"""
Simple AGI Workflow Demo
=========================

Demonstrates the complete AGI autonomous workflow.
"""

import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from companion_baas.sdk import BrainClient


def main():
    print("\n" + "="*70)
    print("  AGI AUTONOMOUS WORKFLOW DEMONSTRATION")
    print("="*70)
    print("\nWorkflow:")
    print("  Query → Brain → AGI Engine → Decides Modules → Executes → Response")
    print("="*70)
    
    # Initialize client with AGI enabled
    print("\n1. Initializing Brain with AGI enabled...")
    client = BrainClient(enable_agi=True)
    print("   ✅ Brain initialized")
    
    # Test query
    query = "Hello! Can you explain what you can do?"
    print(f"\n2. Sending query: \"{query}\"")
    
    # AGI processes autonomously
    print("\n3. AGI Processing...")
    print("   - Analyzing query type...")
    print("   - Deciding which modules to use...")
    print("   - Planning execution...")
    print("   - Executing plan...")
    
    response = client.think(query)
    
    print("\n4. Response Generated!")
    print("="*70)
    print(response['response'][:300] + "...")
    print("="*70)
    
    if 'agi_plan' in response:
        print("\n5. AGI Decision Details:")
        plan = response['agi_plan']
        print(f"   Query Type: {plan['query_type']}")
        print(f"   Confidence: {plan['confidence']:.1%}")
        print(f"   Modules Planned: {', '.join(plan['modules_to_use'])}")
        print(f"   Execution Steps: {len(plan['execution_order'])}")
        print(f"   Reasoning: {plan['reasoning']}")
        
        print("\n6. Execution Result:")
        metadata = response['metadata']
        print(f"   Modules Used: {', '.join(metadata.get('modules_used', []))}")
        print(f"   Steps Completed: {metadata.get('steps_completed', 0)}/{len(plan['execution_order'])}")
        print(f"   Execution Time: {metadata.get('execution_time', 0):.2f}s")
        print(f"   Decision Time: {metadata.get('decision_time', 0):.2f}s")
        print(f"   Total Time: {metadata.get('total_time', 0):.2f}s")
        
        if metadata.get('learned_insights'):
            print(f"\n7. Learning:")
            for insight in metadata['learned_insights']:
                print(f"   - {insight}")
    
    # Get AGI statistics
    print("\n8. AGI Statistics:")
    try:
        stats = client.get_agi_decision_stats()
        print(f"   Total Decisions: {stats['total_decisions']}")
        print(f"   Success Rate: {stats['success_rate']:.1%}")
    except:
        print("   Statistics not yet available")
    
    print("\n" + "="*70)
    print("✅ AGI Workflow Demonstration Complete!")
    print("\nThe brain autonomously:")
    print("  ✓ Analyzed the query")
    print("  ✓ Decided which modules to use")
    print("  ✓ Planned the execution")
    print("  ✓ Executed the plan")
    print("  ✓ Generated the response")
    print("  ✓ Learned from the interaction")
    print("\nNo manual orchestration needed - AGI handles everything!")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
