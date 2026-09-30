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

/** 倒计时秒数 */
const COUNTDOWN_SECONDS = 3;

/** 开始播放时向前预热的秒数（从当前位置前三秒开始） */
const LEAD_SECONDS = 3;

export default class AccompanimentManager extends Manager {
    private timer: number | null = null;

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
        return store.useManager("stateManager")._state.accompanimentMode;
    }

    get listening() {
        return store.useManager("stateManager")._state.accompanimentListening;
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

        // 从当前播放位置前三秒开始播放
        const startSeconds = Math.max(0, store.getSeconds() - LEAD_SECONDS);
        store.setSeconds(startSeconds);
        store.playAudio();

        stateManager._state.accompanimentMode = true;
        stateManager._state.accompanimentListening = false;
        this.beginCountdown();
    }

    private beginCountdown() {
        const stateManager = store.useManager("stateManager");
        let remaining = COUNTDOWN_SECONDS;
        stateManager._state.accompanimentCountdown = remaining;
        this.clearTimer();
        this.timer = window.setInterval(() => {
            remaining -= 1;
            if (remaining <= 0) {
                stateManager._state.accompanimentCountdown = null;
                stateManager._state.accompanimentListening = true;
                this.clearTimer();
            }
            else {
                stateManager._state.accompanimentCountdown = remaining;
            }
        }, 1000);
    }

    private clearTimer() {
        if (this.timer !== null) {
            window.clearInterval(this.timer);
            this.timer = null;
        }
    }

    /** 把当前播放位置的拍数吸附到最近的横网格格点 */
    private snapBeatsToGrid(beatsValue: number): Beats {
        const stateManager = store.useManager("stateManager");
        const intPart = Math.floor(beatsValue);
        const decimal = beatsValue - intPart;
        const fenzi = Math.round(decimal * stateManager._state.horizonalLineCount);
        const fenmu = stateManager._state.horizonalLineCount;
        return [intPart, fenzi, fenmu];
    }

    placeNote(type: NoteType) {
        const stateManager = store.useManager("stateManager");
        if (!stateManager._state.accompanimentMode || !stateManager._state.accompanimentListening) {
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
        this.clearTimer();
        stateManager._state.accompanimentMode = false;
        stateManager._state.accompanimentListening = false;
        stateManager._state.accompanimentCountdown = null;
        store.pauseAudio();
    }
}
