#!/usr/bin/env python3
"""
用户词典管理模块
管理用户自定义词典，提供权重匹配和替换功能
"""

import re
import difflib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import config

class DictionaryManager:
    def __init__(self):
        """初始化词典管理器"""
        self.dictionary_file = config.DICTIONARY_FILE
        self.user_dict: Dict[str, float] = {}
        self.load_dictionary()
        
        # 缓存编译的正则表达式
        self._compiled_patterns: Dict[str, re.Pattern] = {}
        
    def load_dictionary(self) -> bool:
        """加载用户词典"""
        if not self.dictionary_file.exists():
            print(f"词典文件不存在: {self.dictionary_file}")
            self.create_default_dictionary()
            return False
        
        try:
            self.user_dict.clear()
            
            with open(self.dictionary_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # 解析格式: "词汇 权重%"
                    parts = line.rsplit(' ', 1)
                    if len(parts) != 2:
                        print(f"词典文件第 {line_num} 行格式错误: {line}")
                        continue
                    
                    word, weight_str = parts
                    word = word.strip()
                    weight_str = weight_str.strip()
                    
                    # 解析权重
                    if weight_str.endswith('%'):
                        try:
                            weight = float(weight_str[:-1]) / 100.0
                            # 限制权重范围
                            weight = min(weight, config.DICTIONARY_MAX_WEIGHT)
                            weight = max(weight, 0.0)
                            
                            self.user_dict[word] = weight
                            
                        except ValueError:
                            print(f"词典文件第 {line_num} 行权重格式错误: {line}")
                            continue
                    else:
                        print(f"词典文件第 {line_num} 行缺少百分比符号: {line}")
                        continue
            
            print(f"✅ 加载用户词典成功，共 {len(self.user_dict)} 个词汇")
            if config.DEBUG_MODE:
                for word, weight in self.user_dict.items():
                    print(f"  {word}: {weight:.1%}")
            
            return True
            
        except Exception as e:
            print(f"❌ 加载词典文件失败: {e}")
            return False
    
    def create_default_dictionary(self):
        """创建默认词典文件"""
        try:
            default_dict = [
                "# 用户词典文件",
                "# 格式: 词汇 权重%",
                "# 权重范围: 0-50% (避免过度替换)",
                "",
                "测试 40%",
                "侧室 20%",
                "React 30%",
                "JavaScript 35%",
                "Python 30%",
                "API 25%",
                "数据库 30%",
                "算法 25%",
                "前端 20%",
                "后端 20%",
            ]
            
            with open(self.dictionary_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(default_dict))
            
            print(f"✅ 创建默认词典文件: {self.dictionary_file}")
            self.load_dictionary()
            
        except Exception as e:
            print(f"❌ 创建默认词典文件失败: {e}")
    
    def save_dictionary(self) -> bool:
        """保存词典到文件"""
        try:
            lines = [
                "# 用户词典文件",
                "# 格式: 词汇 权重%",
                "# 权重范围: 0-50% (避免过度替换)",
                ""
            ]
            
            # 按词汇排序
            sorted_items = sorted(self.user_dict.items())
            for word, weight in sorted_items:
                lines.append(f"{word} {weight:.0%}")
            
            with open(self.dictionary_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            print(f"✅ 词典已保存: {self.dictionary_file}")
            return True
            
        except Exception as e:
            print(f"❌ 保存词典失败: {e}")
            return False
    
    def add_word(self, word: str, weight: float) -> bool:
        """添加词汇到词典"""
        if not word or not word.strip():
            return False
        
        word = word.strip()
        weight = min(weight, config.DICTIONARY_MAX_WEIGHT)
        weight = max(weight, 0.0)
        
        self.user_dict[word] = weight
        print(f"✅ 添加词汇: {word} ({weight:.1%})")
        
        return self.save_dictionary()
    
    def remove_word(self, word: str) -> bool:
        """从词典中移除词汇"""
        word = word.strip()
        if word in self.user_dict:
            del self.user_dict[word]
            print(f"✅ 移除词汇: {word}")
            return self.save_dictionary()
        else:
            print(f"❌ 词汇不存在: {word}")
            return False
    
    def get_word_weight(self, word: str) -> float:
        """获取词汇的权重"""
        return self.user_dict.get(word.strip(), 0.0)
    
    def _calculate_similarity(self, word1: str, word2: str) -> float:
        """计算两个词汇的相似度"""
        # 使用多种相似度算法的组合
        
        # 1. 字符串相似度 (difflib)
        seq_ratio = difflib.SequenceMatcher(None, word1.lower(), word2.lower()).ratio()
        
        # 2. 长度相似度
        len1, len2 = len(word1), len(word2)
        len_ratio = min(len1, len2) / max(len1, len2) if max(len1, len2) > 0 else 0
        
        # 3. 编辑距离相似度
        def levenshtein_ratio(s1, s2):
            """计算基于编辑距离的相似度"""
            if len(s1) == 0 or len(s2) == 0:
                return 0.0
            
            # 简单的编辑距离计算
            rows = len(s1) + 1
            cols = len(s2) + 1
            dist = [[0 for _ in range(cols)] for _ in range(rows)]
            
            for i in range(1, rows):
                dist[i][0] = i
            for j in range(1, cols):
                dist[0][j] = j
                
            for i in range(1, rows):
                for j in range(1, cols):
                    cost = 0 if s1[i-1] == s2[j-1] else 1
                    dist[i][j] = min(
                        dist[i-1][j] + 1,     # deletion
                        dist[i][j-1] + 1,     # insertion
                        dist[i-1][j-1] + cost # substitution
                    )
            
            max_len = max(len(s1), len(s2))
            return (max_len - dist[rows-1][cols-1]) / max_len
        
        edit_ratio = levenshtein_ratio(word1.lower(), word2.lower())
        
        # 4. 音近相似度（简单版本）
        def simple_phonetic_similarity(s1, s2):
            """简单的音近相似度"""
            # 移除常见的音近字符差异
            phonetic_map = {
                'c': 's', 'k': 'c', 'ph': 'f', 'gh': 'f',
                'tion': 'shun', 'sion': 'zhun'
            }
            
            def normalize_phonetic(s):
                s = s.lower()
                for old, new in phonetic_map.items():
                    s = s.replace(old, new)
                return s
            
            norm1 = normalize_phonetic(s1)
            norm2 = normalize_phonetic(s2)
            return difflib.SequenceMatcher(None, norm1, norm2).ratio()
        
        phonetic_ratio = simple_phonetic_similarity(word1, word2)
        
        # 综合相似度 (加权平均)
        final_similarity = (
            seq_ratio * 0.4 +
            len_ratio * 0.2 +
            edit_ratio * 0.3 +
            phonetic_ratio * 0.1
        )
        
        return final_similarity
    
    def find_best_match(self, word: str) -> Optional[Tuple[str, float, float]]:
        """
        找到最佳匹配的词典词汇
        
        Returns:
            (dict_word, similarity, effective_weight) 或 None
        """
        if not self.user_dict or not word.strip():
            return None
        
        word = word.strip()
        best_match = None
        best_similarity = 0.0
        best_word = ""
        
        for dict_word, weight in self.user_dict.items():
            similarity = self._calculate_similarity(word, dict_word)
            
            # 计算有效权重（相似度 * 词典权重）
            effective_weight = similarity * weight
            
            if effective_weight > best_similarity:
                best_similarity = effective_weight
                best_match = (dict_word, similarity, effective_weight)
                best_word = dict_word
        
        # 检查是否超过阈值
        if best_match and best_match[2] >= config.DICTIONARY_WEIGHT_THRESHOLD:
            return best_match
        
        return None
    
    def process_transcript(self, transcript: List[Dict]) -> List[Dict]:
        """
        处理转录结果，应用词典替换
        
        Args:
            transcript: 转录结果列表
            
        Returns:
            处理后的转录结果
        """
        if not self.user_dict or not transcript:
            return transcript
        
        processed_transcript = []
        
        for entry in transcript:
            original_text = entry.get('text', '').strip()
            if not original_text:
                processed_transcript.append(entry)
                continue
            
            # 分词处理
            words = re.findall(r'\w+|[^\w\s]', original_text)
            processed_words = []
            replacements = []  # 记录替换信息
            
            for word in words:
                if word.isspace() or not word.isalpha():
                    processed_words.append(word)
                    continue
                
                # 查找最佳匹配
                match = self.find_best_match(word)
                if match:
                    dict_word, similarity, effective_weight = match
                    processed_words.append(dict_word)
                    
                    replacements.append({
                        'original': word,
                        'replacement': dict_word,
                        'similarity': similarity,
                        'weight': effective_weight
                    })
                    
                    if config.DEBUG_MODE:
                        print(f"替换: {word} -> {dict_word} (相似度: {similarity:.2f}, 权重: {effective_weight:.2f})")
                else:
                    processed_words.append(word)
            
            # 重建文本
            processed_text = ''.join(processed_words)
            
            # 创建新的条目
            new_entry = entry.copy()
            new_entry['text'] = processed_text
            
            # 添加替换信息（可选）
            if replacements and config.DEBUG_MODE:
                new_entry['replacements'] = replacements
            
            processed_transcript.append(new_entry)
        
        return processed_transcript
    
    def get_dictionary_stats(self) -> Dict:
        """获取词典统计信息"""
        if not self.user_dict:
            return {'total': 0, 'avg_weight': 0.0, 'max_weight': 0.0, 'min_weight': 0.0}
        
        weights = list(self.user_dict.values())
        return {
            'total': len(self.user_dict),
            'avg_weight': sum(weights) / len(weights),
            'max_weight': max(weights),
            'min_weight': min(weights),
            'words': list(self.user_dict.keys())
        }

# 测试代码
if __name__ == "__main__":
    # 启用调试模式
    config.DEBUG_MODE = True
    
    manager = DictionaryManager()
    
    # 显示词典统计
    stats = manager.get_dictionary_stats()
    print(f"\n词典统计:")
    print(f"  总词汇数: {stats['total']}")
    print(f"  平均权重: {stats['avg_weight']:.1%}")
    print(f"  最高权重: {stats['max_weight']:.1%}")
    print(f"  最低权重: {stats['min_weight']:.1%}")
    
    # 测试匹配功能
    test_words = ["测师", "Recat", "javascript", "pai", "算发"]
    
    print(f"\n匹配测试:")
    for word in test_words:
        match = manager.find_best_match(word)
        if match:
            dict_word, similarity, weight = match
            print(f"  {word} -> {dict_word} (相似度: {similarity:.2f}, 有效权重: {weight:.2f})")
        else:
            print(f"  {word} -> 无匹配")
    
    # 测试转录处理
    test_transcript = [
        {'start': 0.0, 'duration': 2.0, 'text': '这是一个测师的Recat应用'},
        {'start': 2.0, 'duration': 3.0, 'text': '使用javascript和pai进行开发'},
        {'start': 5.0, 'duration': 2.0, 'text': '需要好的算发和数据苦'}
    ]
    
    print(f"\n转录处理测试:")
    processed = manager.process_transcript(test_transcript)
    for entry in processed:
        print(f"  原文: {test_transcript[processed.index(entry)]['text']}")
        print(f"  处理后: {entry['text']}")
        print()