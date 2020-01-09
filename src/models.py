import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision

__all__ = ['ConvLSTM']


class Encoder(nn.Module):
    def __init__(self, latent_dim):
        super(Encoder, self).__init__()
        model = torchvision.models.vgg19(pretrained=True)

        self.features = model.features
        self.classifier = nn.Sequential(
            *list(model.classifier.children())[:-1])
        last_layer = list(model.classifier.children())[-1]
        self.fc = nn.Linear(last_layer.in_features, latent_dim)

    def forward(self, x):
        with torch.no_grad():
            x = self.features(x)
            x = x.view(x.shape[0], -1)
            x = self.classifier(x)
        return self.fc(x)


class LSTM(nn.Module):
    def __init__(self, latent_dim, num_layers, hidden_dim, bidirectional):
        super(LSTM, self).__init__()
        self.lstm = nn.LSTM(latent_dim, hidden_dim, num_layers,
                            batch_first=True, bidirectional=bidirectional)
        self.hidden_state = None

    def reset_hidden_state(self):
        self.hidden_state = None

    def forward(self, x):
        x, self.hidden_state = self.lstm(x, self.hidden_state)
        return x


class ConvLSTM(nn.Module):
    """ Convolitional LSTM model for video predictions
    """

    def __init__(
        self, num_classes, latent_dim=512, lstm_layers=1, hidden_dim=1024,
            bidirectional=True, attention=True
    ):
        """ Inintialization
        Parameters
        ----------
        num_classes : int
            Number of output classes
        latent_dim : int
            Latent dimension for embeddings fed into LSTMs
        lstm_layers : int
            Number of lstm layers to use in model
        hidden_dim : int
            Hidden kayer dimension in final prediction block
        bidirectional : bool
            Bi/Unidrectional switch
        attention : bool
            Attention block switch
        Returns
        -------
        """
        super(ConvLSTM, self).__init__()
        self.encoder = Encoder(latent_dim)
        self.lstm = LSTM(latent_dim, lstm_layers, hidden_dim, bidirectional)
        self.output_layers = nn.Sequential(
            nn.Linear(
                2 * hidden_dim if bidirectional else hidden_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim, momentum=0.01),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_classes),
            nn.Softmax(dim=-1),
        )
        self.attention = attention
        self.attention_layer = nn.Linear(
            2 * hidden_dim if bidirectional else hidden_dim, 1)

    def forward(self, x):
        """ Forward pass
        Parameters
        ----------
        x : torch.tensor
            Tensor with video frames, expected size (bs, n_frames, c, h, w)
        Returns
        -------
        x : torch.tensor
            Processed torch data
        """
        batch_size, seq_length, c, h, w = x.shape
        x = x.view(batch_size * seq_length, c, h, w)
        x = self.encoder(x)
        x = x.view(batch_size, seq_length, -1)
        x = self.lstm(x)
        if self.attention:
            attention_w = F.softmax(
                self.attention_layer(x).squeeze(-1), dim=-1)
            x = torch.sum(attention_w.unsqueeze(-1) * x, dim=1)
        else:
            x = x[:, -1]
        return self.output_layers(x)
