#!/usr/bin/env python3
"""
Summary Generator
=================

Generates detailed summaries of autonomous changes
"""

import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """Generate change summaries"""
    
    def __init__(self):
        logger.info("📝 Summary Generator initialized")
    
    def generate_summary(self, 
                        trigger: str,
                        analysis: str,
                        decision: str,
                        changes: List[Dict[str, Any]],
                        impact: Dict[str, Any],
                        commit_hash: str) -> str:
        """
        Generate detailed change summary
        
        Returns formatted markdown summary
        """
        summary = f"""
🤖 AUTONOMOUS MODIFICATION SUMMARY
Timestamp: {datetime.now().isoformat()}
Commit: {commit_hash[:8]}

TRIGGER: {trigger}
ANALYSIS: {analysis}
DECISION: {decision}

CHANGES:
"""
        
        for change in changes:
            summary += f"✏️  {change['type']}: {change['file']}\n"
            if 'details' in change:
                for detail in change['details']:
                    summary += f"    - {detail}\n"
        
        summary += f"""
📊 IMPACT:
"""
        for key, value in impact.items():
            summary += f"    - {key}: {value}\n"
        
        summary += f"""
🔄 ROLLBACK: git revert {commit_hash[:8]}
"""
        
        logger.info("✅ Summary generated")
        return summary
