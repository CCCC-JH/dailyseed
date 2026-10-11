package com.dailyseed;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * DailySeed 后端。
 *
 * <p>设计原则（见《DailySeed-产品设计文档.md》）：
 * <ul>
 *   <li>模块化单体，不上微服务；无 Redis、无 MQ、无定时任务</li>
 *   <li>懒生成：用户点开才生成今天的卡，不用 cron</li>
 *   <li>幂等：同一用户同一天永远得到同一张卡（唯一例外是放纵日主动换卡，见 §5.5）</li>
 * </ul>
 */
@SpringBootApplication
public class DailySeedApplication {

    public static void main(String[] args) {
        SpringApplication.run(DailySeedApplication.class, args);
    }
}
