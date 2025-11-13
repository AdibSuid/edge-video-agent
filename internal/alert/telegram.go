package alert

import (
	"fmt"
	"time"

	"github.com/yourorg/edge-video-agent/internal/config"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	log "github.com/sirupsen/logrus"
)

type AlertLevel string

const (
	AlertInfo    AlertLevel = "INFO"
	AlertWarning AlertLevel = "WARNING"
	AlertError   AlertLevel = "ERROR"
)

type TelegramAlerter struct {
	bot    *tgbotapi.BotAPI
	chatID int64
}

func NewTelegramAlerter(cfg config.TelegramConfig) (*TelegramAlerter, error) {
	bot, err := tgbotapi.NewBotAPI(cfg.BotToken)
	if err != nil {
		return nil, fmt.Errorf("failed to create Telegram bot: %w", err)
	}

	log.Infof("Telegram bot authorized: @%s", bot.Self.UserName)

	return &TelegramAlerter{
		bot:    bot,
		chatID: cfg.ChatID,
	}, nil
}

func (ta *TelegramAlerter) SendAlert(level AlertLevel, title, message string) error {
	emoji := "ℹ️"
	switch level {
	case AlertWarning:
		emoji = "⚠️"
	case AlertError:
		emoji = "🚨"
	}

	formattedMsg := fmt.Sprintf("%s *%s: %s*\n\n%s\n\n_Time: %s_",
		emoji,
		level,
		title,
		message,
		time.Now().Format("2006-01-02 15:04:05"),
	)

	msg := tgbotapi.NewMessage(ta.chatID, formattedMsg)
	msg.ParseMode = "Markdown"

	if _, err := ta.bot.Send(msg); err != nil {
		return fmt.Errorf("failed to send Telegram message: %w", err)
	}

	log.WithFields(log.Fields{
		"level": level,
		"title": title,
	}).Debug("Telegram alert sent")

	return nil
}

func (ta *TelegramAlerter) SendAlertWithDetails(level AlertLevel, title string, details map[string]string) error {
	message := ""
	for key, value := range details {
		message += fmt.Sprintf("*%s:* %s\n", key, value)
	}

	return ta.SendAlert(level, title, message)
}