import os
import json
import numpy as np
import traceback
from pathlib import Path

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    AutoModelForCausalLM
)
from transformers.onnx import export, FeaturesManager
from sentence_transformers import SentenceTransformer
import onnxruntime as ort

DATA = os.environ['IEXEC_DATASET_FILENAME']
INPUT_QUESTION = "/iexec_in/question.txt"
OUTPUT_FILE = "/iexec_out/result.txt"
iexec_out = os.environ['IEXEC_OUT']
iexec_in = os.environ['IEXEC_IN']

# ========== Safe JSON Encoder ==========
class EnhancedEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (np.float32, np.float64)):
            return float(o)
        return super().default(o)

# ========== EXPORT ONNX ==========
def export_emotion_model_onnx(output_path="onnx-emotion/model.onnx"):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        print("✅ ONNX model already exported.")
        return str(output_path)

    print("📦 Exporting ONNX model...")

    model_id = "j-hartmann/emotion-english-distilroberta-base"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(model_id)

    feature = "sequence-classification"
    _, model_onnx_config = FeaturesManager.check_supported_model_or_raise(model, feature=feature)
    onnx_config = model_onnx_config(model.config)

    export(
        preprocessor=tokenizer,
        model=model,
        config=onnx_config,
        opset=14,
        output=output_path
    )

    print("✅ ONNX export complete.")
    return str(output_path)

# ========== Emotion Analysis ==========
def analyse_emotion(text, onnx_path="onnx-emotion/model.onnx"):
    onnx_path = export_emotion_model_onnx(onnx_path)
    tokenizer = AutoTokenizer.from_pretrained("j-hartmann/emotion-english-distilroberta-base")
    inputs = tokenizer(text, return_tensors="np", padding=True, truncation=True)

    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    ort_inputs = {k: v for k, v in inputs.items()}
    logits = session.run(None, ort_inputs)[0][0]
    probs = np.exp(logits) / np.sum(np.exp(logits))

    labels = ['anger', 'disgust', 'fear', 'joy', 'neutral', 'sadness', 'surprise']
    return dict(zip(labels, probs.round(3)))

# ========== Embedding ==========
def get_embedding(text):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    return model.encode(text).tolist()

# ========== LLM Hint ==========
def chat_response_hint(prompt):
    return f"(à exécuter dans enclave TDX : ./main -m mistral-7b.q4_K_M.gguf -p \"{prompt}\" -t 8)"

def generate_response(question, emotion_map):
    print("🚀 Starting generation...", flush=True)
    dominant_emotion = max(emotion_map, key=emotion_map.get)

    emotion_prefix = {
        "joy": "Answer positively and enthusiastically.",
        "sadness": "Answer in a comforting and encouraging way.",
        "anger": "Answer calmly and respectfully.",
        "fear": "Answer in a reassuring and confident tone.",
        "disgust": "Answer in a neutral and respectful tone.",
        "surprise": "Answer with curiosity and interest.",
        "neutral": "Answer factually."
    }

    tone = emotion_prefix.get(dominant_emotion, "Answer clearly.")
    prompt = f"{tone}\nQ: {question}\nA:"
    print(f"🎯 Prompt used:\n{prompt}\n", flush=True)

    try:
        tokenizer = AutoTokenizer.from_pretrained("distilgpt2")
        model = AutoModelForCausalLM.from_pretrained("distilgpt2")

        inputs = tokenizer(prompt, return_tensors="pt")
        output_ids = model.generate(
            inputs["input_ids"],
            max_new_tokens=40,
            do_sample=False,
            temperature=0.7,
            top_k=40,
            repetition_penalty=1.1
        )

        output = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        answer = output.split("A:")[-1].strip()
        if "." in answer:
            answer = answer.split(".")[0].strip() + "."

        print("✅ Generation complete:", answer, flush=True)
        return answer

    except Exception as e:
        print(f"❌ Generation failed: {e}", flush=True)
        traceback.print_exc()
        return "⚠️ Generation failed."


# ========== MAIN ==========
def main():
    try:
        DATA = os.environ.get('IEXEC_DATASET_FILENAME')
        iexec_out = os.environ.get('IEXEC_OUT', '/iexec_out')
        iexec_in = os.environ.get('IEXEC_IN', '/iexec_in')
        input_file = os.path.join(iexec_in, DATA)
        question_file = INPUT_QUESTION

        print(f"DATA: {DATA}", flush=True)
        print(f"INPUT_QUESTION: {question_file}", flush=True)
        print(f"OUTPUT_FILE: {OUTPUT_FILE}", flush=True)
        print(f"iexec_out: {iexec_out}", flush=True)
        print(f"iexec_in: {iexec_in}", flush=True)

        if not DATA:
            raise EnvironmentError("IEXEC_DATASET_FILENAME is not set")
        if not os.path.exists(input_file):
            raise FileNotFoundError(input_file)
        if not os.path.exists(question_file):
            raise FileNotFoundError(question_file)

        with open(input_file, "r") as f:
            emotion_text = f.read().strip()
        with open(question_file, "r") as f:
            question_text = f.read().strip()

        if len(emotion_text) < 5 or len(question_text) < 5:
            raise ValueError("Text too short for analysis or generation.")

        print("🧠 Emotion input:", emotion_text[:80] + "..." if len(emotion_text) > 80 else emotion_text, flush=True)
        print("❓ Question input:", question_text[:80] + "..." if len(question_text) > 80 else question_text, flush=True)

        emotions = analyse_emotion(emotion_text)

        try:
            embedding = get_embedding(emotion_text)
        except Exception as e:
            print(f"❌ Embedding generation failed: {e}", flush=True)
            traceback.print_exc()
            embedding = []

        generation_hint = chat_response_hint(question_text)
        generated_response = generate_response(question_text, emotions)

        result = {
            "emotion_input": emotion_text,
            "input_question": question_text,
            "emotion": {k: float(v) for k, v in emotions.items()},
            "embedding_preview": [float(x) for x in embedding[:10]],
            "generation_hint": generation_hint,
            "generated_response": generated_response
        }

        Path(iexec_out).mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(result, f, indent=2, cls=EnhancedEncoder)
            f.flush()
            os.fsync(f.fileno())

        with open(os.path.join(iexec_out, 'computed.json'), 'w') as f:
            json.dump({ "deterministic-output-path": OUTPUT_FILE }, f)
            f.flush()
            os.fsync(f.fileno())

        print("✅ Output written to", OUTPUT_FILE, flush=True)

    except Exception as e:
        print(f"❌ Error during execution: {e}", flush=True)
        traceback.print_exc()

        fallback = {
            "status": "failed",
            "error": str(e)
        }
        try:
            Path(iexec_out).mkdir(parents=True, exist_ok=True)
            with open(OUTPUT_FILE, "w") as f:
                json.dump(fallback, f, indent=2)
            with open(os.path.join(iexec_out, 'computed.json'), 'w') as f:
                json.dump({ "deterministic-output-path": OUTPUT_FILE }, f)
        except Exception as sub_e:
            print(f"❌ Failed to write fallback output: {sub_e}", flush=True)
            traceback.print_exc()


if __name__ == "__main__":
    main()
