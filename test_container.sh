#!/bin/bash

# Test alle Worker-Imports in laufenden Containern
echo "🔍 Testing Worker Imports..."

workers=(
    "telegram-worker"
    "translation-worker" 
    "image-worker"
    "audio-worker"
    "emotion-worker"
    "classification-worker"
    "geolocation-worker"
)

imports=(
    "workers.telegram_scraper.worker"
    "workers.translation_worker.worker"
    "workers.image_worker.worker"
    "workers.audio_worker.worker"
    "workers.emotion_worker.worker"
    "workers.classification_worker.worker"
    "workers.geolocation_worker.worker"
)

functions=(
    "scrape_telegram_job"
    "translate_and_update_job"
    "analyze_and_update"
    "transcribe_and_update"
    "classify_emotion_job"
    "classify_post_job"
    "extract_and_update_location"
)

for i in "${!workers[@]}"; do
    worker="${workers[$i]}"
    import="${imports[$i]}"
    func="${functions[$i]}"
    
    echo ""
    echo "======================================"
    echo "Testing: $worker"
    echo "======================================"
    
    # Test Import
    container=$(docker ps --filter "name=$worker" --format "{{.Names}}" | head -n1)
    
    if [ -z "$container" ]; then
        echo "❌ Container $worker not running"
        continue
    fi
    
    echo "📦 Container: $container"
    
    # Test Module Import
    docker exec "$container" python -c "import $import; print('✅ Import successful')" 2>&1 | head -n 20
    
    # Test Function Access
    docker exec "$container" python -c "from $import import $func; print('✅ Function $func found')" 2>&1 | head -n 5
done

echo ""
echo "======================================"
echo "✅ Test Complete"
echo "======================================"