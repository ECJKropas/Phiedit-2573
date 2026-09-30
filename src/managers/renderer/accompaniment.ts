/**
 * @license MIT
 * Copyright © 2025 程序小袁_2573. All rights reserved.
 * Licensed under MIT (https://opensource.org/licenses/MIT)
 */

/* eslint-disable no-magic-numbers */

import globalEventEmitter from "@/eventEmitter";
import { NoteType, NoteFake, NoteAbove } from "@/models/note";
import { Beats } from "@/models/beats";
import store from "@/store";
import Manager from "./abstract";
import { createCatchErrorByMessage } from "@/tools/catchError";

/** 倒计时秒数（与向前预热秒数一致） */
const COUNTDOWN_SECONDS = 3;

/** 开始播放时向前预热的秒数（从当前位置前三秒开始） */
const LEAD_SECONDS = 3;

export default class AccompanimentManager extends Manager {
    private rafId: number | null = null;

    /** 点击开始时记录的「开始位置」（秒）：播放头到达此处才切到监听 */
    private startPosition = 0;

    constructor() {
        super();
        globalEventEmitter.on("ACCOMPANIMENT_TOGGLE", createCatchErrorByMessage(() => {
            this.toggle();
        }, "切换伴随创作"));
        globalEventEmitter.on("ACCOMPANIMENT_STOP", createCatchErrorByMessage(() => {
            this.stop();
        }, "停止伴随创作"));
        globalEventEmitter.on("ACCOMPANIMENT_PLACE", createCatchErrorByMessage((type: NoteType) => {
            this.placeNote(type);
        }, "伴随创作放置音符"));
    }

    get enabled() {
        return store.useManager("stateManager").state.accompanimentMode;
    }

    get listening() {
        return store.useManager("stateManager").state.accompanimentListening;
    }

    toggle() {
        if (this.enabled) {
            this.stop();
        }
        else {
            this.start();
        }
    }

    start() {
        const stateManager = store.useManager("stateManager");

        // 记录点击时的「开始位置」，播放头到达此处才切到监听
        this.startPosition = store.getSeconds();

        // 倒带前三秒开始播放音乐，但先不监听
        const startSeconds = Math.max(0, this.startPosition - LEAD_SECONDS);
        store.setSeconds(startSeconds);
        store.playAudio();

        // 通过响应式代理 state 写值，确保 Vue 模板（按钮/覆盖层）会更新
        stateManager.state.accompanimentMode = true;
        stateManager.state.accompanimentListening = false;
        stateManager.state.accompanimentCountdown = COUNTDOWN_SECONDS;

        this.beginWatch();
    }

    /**
     * 每帧检查播放头位置：距离开始位置还有多少秒就显示 3→2→1，
     * 播放头恰好到达开始位置时切到监听。相比固定墙钟计时，能严格对齐音乐进度。
     */
    private beginWatch() {
        this.clearRaf();
        const tick = () => {
            const stateManager = store.useManager("stateManager");
            if (!stateManager.state.accompanimentMode) {
                return;
            }

            const remaining = this.startPosition - store.getSeconds();
            if (remaining > 0) {
                stateManager.state.accompanimentCountdown =
                    Math.min(COUNTDOWN_SECONDS, Math.max(1, Math.ceil(remaining)));
                stateManager.state.accompanimentListening = false;
                this.rafId = window.requestAnimationFrame(tick);
            }
            else {
                stateManager.state.accompanimentCountdown = null;
                stateManager.state.accompanimentListening = true;
                this.clearRaf();
            }
        };
        this.rafId = window.requestAnimationFrame(tick);
    }

    private clearRaf() {
        if (this.rafId !== null) {
            window.cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }
    }

    /** 把当前播放位置的拍数吸附到最近的横网格格点 */
    private snapBeatsToGrid(beatsValue: number): Beats {
        const stateManager = store.useManager("stateManager");
        const intPart = Math.floor(beatsValue);
        const decimal = beatsValue - intPart;
        const fenzi = Math.round(decimal * stateManager.state.horizonalLineCount);
        const fenmu = stateManager.state.horizonalLineCount;
        return [intPart, fenzi, fenmu];
    }

    placeNote(type: NoteType) {
        const stateManager = store.useManager("stateManager");
        if (!stateManager.state.accompanimentMode || !stateManager.state.accompanimentListening) {
            return;
        }

        const coordinateManager = store.useManager("coordinateManager");
        const mouseManager = store.useManager("mouseManager");
        const historyManager = store.useManager("historyManager");

        const snappedBeats = this.snapBeatsToGrid(store.getCurrentBeatsValue());

        // 横向位置：跟随鼠标并吸附到竖线，未悬停画布时落在中线
        const positionX = mouseManager.isHovering ?
            coordinateManager.attatchX(mouseManager.mouseX) :
            0;

        const addedNote = store.addNote({
            startTime: [...snappedBeats],
            endTime: [...snappedBeats],
            positionX,
            type,
            speed: 1,
            alpha: 255,
            size: 1,
            visibleTime: 999999,
            yOffset: 0,
            isFake: NoteFake.Real,
            above: NoteAbove.Above,
            judgeArea: 1,
        }, stateManager.state.currentJudgeLineNumber);
        historyManager.recordAddNote(addedNote.id);
    }

    stop() {
        const stateManager = store.useManager("stateManager");
        this.clearRaf();

        // 通过响应式代理 state 写值
        stateManager.state.accompanimentMode = false;
        stateManager.state.accompanimentListening = false;
        stateManager.state.accompanimentCountdown = null;
        store.pauseAudio();
    }
}
