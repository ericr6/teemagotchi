import os
import json
import numpy as np
from pathlib import Path

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    AutoModelForCausalLM
)
from transformers.onnx import export, FeaturesManager
from sentence_transformers import SentenceTransformer
import onnxruntime as ort

DATA = "/iexec_in/data.txt"
INPUT_QUESTION = "/iexec_in/question.txt"
OUTPUT_FILE = "/iexec_out/result.txt"

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

# ========== LLM Hint for TDX ==========
def chat_response_hint(prompt):
    return f"(à exécuter dans enclave TDX : ./main -m mistral-7b.q4_K_M.gguf -p \"{prompt}\" -t 8)"

# ========== Falcon-based Generation ==========
def generate_response(question, emotion_map):
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

    # Format: <Tone>\nQ:...\nA:
    prompt = f"{tone}\nQ: {question}\nA:"

    print(f"🎯 Prompt used:\n{prompt}\n")

    tokenizer = AutoTokenizer.from_pretrained("tiiuae/falcon-rw-1b")
    model = AutoModelForCausalLM.from_pretrained("tiiuae/falcon-rw-1b")

    inputs = tokenizer(prompt, return_tensors="pt")
    output_ids = model.generate(
        inputs["input_ids"],
        max_new_tokens=40,  # limit to short, direct answer
        do_sample=False,    # deterministic output
        temperature=0.5,
        top_k=40,
        repetition_penalty=1.2
    )

    output = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    answer = output.split("A:")[-1].strip()

    # Postprocess: cut off verbose generations
    if "." in answer:
        answer = answer.split(".")[0].strip() + "."

    return answer


# ========== MAIN ==========
def main():
    try:
        with open(DATA, "r") as f:
            emotion_text = f.read().strip()
        with open(INPUT_QUESTION, "r") as f:
            question_text = f.read().strip()
    except FileNotFoundError as e:
        print(f"❌ Missing input file: {e.filename}")
        return

    if len(emotion_text) < 5 or len(question_text) < 5:
        print("❌ Text too short for analysis or generation.")
        return

    print("🧠 Emotion input:", emotion_text[:80] + "..." if len(emotion_text) > 80 else emotion_text)
    print("❓ Question input:", question_text[:80] + "..." if len(question_text) > 80 else question_text)

    emotions = analyse_emotion(emotion_text)
    embedding = get_embedding(emotion_text)
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

    Path("/iexec_out").mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    print("✅ Output written to", OUTPUT_FILE)

if __name__ == "__main__":
    main()
