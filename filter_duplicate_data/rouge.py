from ragas.dataset_schema import SingleTurnSample
from ragas.metrics._rouge_score import RougeScore
import asyncio

class Rouge:
    def __init__(self):
        self.rouge_scorer = RougeScore()

    async def calculate_rouge_score(self, reference: str, response: str) -> float:
        """Calculate ROUGE-L F1 score using RAGAS RougeScore"""

        try:
            if not reference or not response:
                return 0.0
            
            sample = SingleTurnSample(
                response=response.strip(),
                reference=reference.strip()
            )

            rouge_score = await self.rouge_scorer.single_turn_ascore(sample)
            return float(rouge_score)
        except Exception as e:
            print(f"Error calculating ROUGE score: {e}")
            return 0.0
    
    def threading_calculation(self, reference: str, response: str) -> float:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.calculate_rouge_score(reference, response))
            loop.close()
            return result
        except Exception as e:
            print(f"Error in ROUGE score calculation wrapper: {e}")
            return 0.0
        
    


if __name__ == '__main__':
    rouge = Rouge()

    name_1 = "Xiaomi POCO X6 Pro 5G 8GB 256GB - Chỉ có tại CellphoneS" # Xiaomi POCO X6 Pro 5G 8GB 256GB - Chỉ có tại CellphoneS , iPhone 16e 256GB | Chính hãng VN/A
    name_2 = "Samsung Galaxy A73 (5G) 256GB - Chỉ có tại CellphoneS" # iPhone 16e 512GB | Chính hãng VN/A , Samsung Galaxy A73 (5G) 256GB - Chỉ có tại CellphoneS

    print(rouge.threading_calculation(name_1, name_2))

    