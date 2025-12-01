#!/usr/bin/env python3
"""
AI 컨설팅 문서 10개 분석 스크립트
각 문서의 핵심 내용을 추출하고 요약
"""

import os
from pathlib import Path

# 파일 목록
files = [
    "/home/ubuntu/upload/chatgpt_1201.txt",
    "/home/ubuntu/upload/chatgpt_1201_2.txt",
    "/home/ubuntu/upload/chatgpt_1201_3.txt",
    "/home/ubuntu/upload/chatgpt_1201_4.txt",
    "/home/ubuntu/upload/claude_1201.txt",
    "/home/ubuntu/upload/gemini_1201.txt",
    "/home/ubuntu/upload/gemini_1201_2.txt",
    "/home/ubuntu/upload/grok_1201_1.txt",
    "/home/ubuntu/upload/grok_1201_2.txt",
    "/home/ubuntu/upload/manus_1201_2.md",
]

output_dir = Path("/home/ubuntu/ares7-ensemble/ai_consultation_analysis")
output_dir.mkdir(exist_ok=True)

# 각 파일 분석
for filepath in files:
    filename = Path(filepath).name
    print(f"\n{'='*80}")
    print(f"분석 중: {filename}")
    print(f"{'='*80}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 기본 통계
        lines = content.split('\n')
        words = content.split()
        chars = len(content)
        
        print(f"줄 수: {len(lines):,}")
        print(f"단어 수: {len(words):,}")
        print(f"문자 수: {chars:,}")
        
        # 처음 500자 미리보기
        print(f"\n[처음 500자 미리보기]")
        print(content[:500])
        print("...")
        
        # 마지막 500자 미리보기
        print(f"\n[마지막 500자 미리보기]")
        print("...")
        print(content[-500:])
        
    except Exception as e:
        print(f"오류 발생: {e}")

print(f"\n{'='*80}")
print("분석 완료")
print(f"{'='*80}")
