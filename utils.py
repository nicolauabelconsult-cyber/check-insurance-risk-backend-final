"""
Utilitários para análise de risco
"""
import re
from typing import Dict, List, Any
from database import execute_query
import unicodedata

def normalize_name(name: str) -> str:
    """Normalizar nome para comparação"""
    if not name:
        return ""
    
    # Remove acentos
    name = unicodedata.normalize('NFD', name)
    name = ''.join(char for char in name if unicodedata.category(char) != 'Mn')
    
    # Maiúsculo e remove espaços extras
    name = re.sub(r'\s+', ' ', name.upper().strip())
    
    return name

def calculate_similarity(name1: str, name2: str) -> float:
    """Calcular similaridade entre nomes"""
    name1 = normalize_name(name1)
    name2 = normalize_name(name2)
    
    if not name1 or not name2:
        return 0.0
    
    # Algoritmo simples de similaridade
    words1 = set(name1.split())
    words2 = set(name2.split())
    
    if len(words1) == 0 or len(words2) == 0:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)

def perform_matching(search_data: Dict[str, str]) -> List[Dict[str, Any]]:
    """Realizar busca por matches nas bases de dados"""
    matches = []
    
    try:
        # Buscar por nome
        if search_data.get('full_name'):
            name_matches = execute_query("""
                SELECT 
                    id, full_name, nif, passport, resident_card, 
                    position, country, additional_info,
                    s.name as source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true
                AND LOWER(ne.full_name) LIKE LOWER(%s)
            """, (f"%{search_data['full_name']}%",))
            
            for match in name_matches:
                similarity = calculate_similarity(search_data['full_name'], match['full_name'])
                if similarity > 0.3:  # Threshold de similaridade
                    matches.append({
                        'type': 'name_match',
                        'similarity': similarity,
                        'source': match['source_name'],
                        'source_type': match['source_type'],
                        'full_name': match['full_name'],
                        'nif': match['nif'],
                        'passport': match['passport'],
                        'position': match['position'],
                        'country': match['country'],
                        'additional_info': match['additional_info']
                    })
        
        # Buscar por NIF
        if search_data.get('nif'):
            nif_matches = execute_query("""
                SELECT 
                    ne.*, s.name as source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true AND ne.nif = %s
            """, (search_data['nif'],))
            
            for match in nif_matches:
                matches.append({
                    'type': 'nif_match',
                    'similarity': 1.0,
                    'source': match['source_name'],
                    'source_type': match['source_type'],
                    'full_name': match['full_name'],
                    'nif': match['nif'],
                    'position': match['position'],
                    'country': match['country']
                })
        
        # Buscar por Passaporte
        if search_data.get('passport'):
            passport_matches = execute_query("""
                SELECT 
                    ne.*, s.name as source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true AND ne.passport = %s
            """, (search_data['passport'],))
            
            for match in passport_matches:
                matches.append({
                    'type': 'passport_match',
                    'similarity': 1.0,
                    'source': match['source_name'],
                    'source_type': match['source_type'],
                    'full_name': match['full_name'],
                    'passport': match['passport'],
                    'position': match['position'],
                    'country': match['country']
                })
        
        # Buscar por Cartão de Residente
        if search_data.get('resident_card'):
            card_matches = execute_query("""
                SELECT 
                    ne.*, s.name as source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true AND ne.resident_card = %s
            """, (search_data['resident_card'],))
            
            for match in card_matches:
                matches.append({
                    'type': 'resident_card_match',
                    'similarity': 1.0,
                    'source': match['source_name'],
                    'source_type': match['source_type'],
                    'full_name': match['full_name'],
                    'resident_card': match['resident_card'],
                    'position': match['position'],
                    'country': match['country']
                })
    
    except Exception as e:
        print(f"Erro na busca por matches: {e}")
    
    return matches

def calculate_risk_score(matches: List[Dict[str, Any]], has_nif: bool = False) -> Dict[str, Any]:
    """Calcular score de risco baseado nos matches"""
    base_score = 0
    risk_factors = []
    
    # Sem matches = baixo risco
    if not matches:
        return {
            'score': 10,
            'level': 'LOW',
            'factors': ['Nenhum match encontrado nas bases de dados']
        }
    
    # Analisar tipos de match
    for match in matches:
        match_type = match.get('type', '')
        source_type = match.get('source_type', '')
        similarity = match.get('similarity', 0.0)
        
        # Pontuação por tipo de source
        if source_type == 'PEP':
            base_score += 40
            risk_factors.append(f"Match em lista PEP: {match.get('full_name', 'N/A')}")
        elif source_type == 'SANCTIONS':
            base_score += 50
            risk_factors.append(f"Match em lista de sanções: {match.get('full_name', 'N/A')}")
        elif source_type == 'FRAUD':
            base_score += 60
            risk_factors.append(f"Match em lista de fraude: {match.get('full_name', 'N/A')}")
        elif source_type == 'CLAIMS':
            base_score += 30
            risk_factors.append(f"Histórico de sinistros: {match.get('full_name', 'N/A')}")
        
        # Pontuação por tipo de match
        if match_type in ['nif_match', 'passport_match', 'resident_card_match']:
            base_score += 20  # Match exato é mais grave
        elif match_type == 'name_match' and similarity > 0.8:
            base_score += 15  # Nome muito similar
        elif match_type == 'name_match' and similarity > 0.5:
            base_score += 10  # Nome similar
    
    # Bonus por ter NIF (maior rastreabilidade)
    if has_nif:
        base_score += 5
        risk_factors.append("Possui NIF para verificação")
    
    # Normalizar score (0-100)
    final_score = min(100, max(0, base_score))
    
    # Determinar nível de risco
    if final_score <= 25:
        risk_level = 'LOW'
    elif final_score <= 50:
        risk_level = 'MEDIUM'
    elif final_score <= 75:
        risk_level = 'HIGH'
    else:
        risk_level = 'CRITICAL'
    
    return {
        'score': final_score,
        'level': risk_level,
        'factors': risk_factors
    }
