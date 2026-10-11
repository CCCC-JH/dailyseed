package com.dailyseed.card;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

/**
 * 科普文案（卡片「?」展开后的第 ④ 段）。
 *
 * <p>刻意不建表：它是稳定的静态文案，卡片只用 {@code science_key} 引用，
 * 来源是《DailySeed-卡片库v2.md》的 10.3，由 tools/gen_seed.py 生成（设计文档 §3.6）。
 */
@Component
public class ScienceNotes {

    public record Note(String key, String title, String body, String source) {
    }

    private final Map<String, Note> byKey;

    public ScienceNotes(ObjectMapper json) {
        try (InputStream in = new ClassPathResource("science-notes.json").getInputStream()) {
            List<Note> notes = json.readValue(in, new TypeReference<List<Note>>() {
            });
            this.byKey = notes.stream().collect(Collectors.toUnmodifiableMap(Note::key, n -> n));
        } catch (IOException e) {
            throw new IllegalStateException("science-notes.json 读取失败（应由 tools/gen_seed.py 生成）", e);
        }
    }

    public Optional<Note> get(String key) {
        return key == null ? Optional.empty() : Optional.ofNullable(byKey.get(key));
    }

    public int size() {
        return byKey.size();
    }
}
